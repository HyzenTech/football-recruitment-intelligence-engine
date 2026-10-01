"""Canonicalize one pinned cohort; outputs remain unvalidated for football analytics."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from football_recruitment.config import ProjectSettings
from football_recruitment.domain.ids import make_id
from football_recruitment.ingestion.storage import (
    IngestionError,
    SnapshotStore,
    cohort_lock,
    digest,
    immutable_write,
    json_bytes,
    within,
)
from football_recruitment.providers.statsbomb import MAPPING_VERSION, StatsBombOpenDataProvider


def write_partition(root, kind, key, records):
    data = b"".join(json_bytes(r.model_dump(mode="json")) for r in records)
    sha = digest(data)
    relative = f"{kind}/{key}/{sha}.jsonl"
    immutable_write(root / relative, data, root)
    return {
        "kind": kind,
        "key": key,
        "path": relative,
        "sha256": sha,
        "byte_count": len(data),
        "record_count": len(records),
    }


def check_match_records(match, events, lineups):
    """Basic referential checks for mapping, not minutes/football semantics validation."""
    teams = {match.home_team_id, match.away_team_id}
    if {t.team.team_id for t in lineups} != teams:
        raise IngestionError("Lineup teams differ from match metadata")
    if len(events) != len({e.event_id for e in events}):
        raise IngestionError("Duplicate event IDs")
    if [e.index for e in events] != list(range(1, len(events) + 1)):
        raise IngestionError("Event indices are not contiguous/source-ordered")
    roster = {t.team.team_id: {p.player.player_id for p in t.entries} for t in lineups}
    for event in events:
        if event.team_id and event.team_id not in teams:
            raise IngestionError("Event team differs from match teams")
        if event.player_id and event.player_id not in roster.get(event.team_id, set()):
            raise IngestionError("Event actor is absent from its team sheet")
        if event.replacement_player_id and event.replacement_player_id not in roster.get(
            event.team_id, set()
        ):
            raise IngestionError("Replacement is absent from its team sheet")
        if any(p.player_id not in roster.get(event.team_id, set()) for p in event.tactical_lineup):
            raise IngestionError("Tactical actor is absent from its team sheet")


def ingest_cohort(
    settings: ProjectSettings,
    project_root: Path,
    *,
    offline=False,
    limit=None,
    workers=2,
    progress=None,
    fetcher=None,
):
    """Resume verified caches; publish a content-addressed manifest only on success."""
    if not 1 <= workers <= 4 or (limit is not None and limit < 1):
        raise IngestionError("Use 1..4 workers and a positive optional match limit")
    dataset = settings.dataset
    project_root = project_root.resolve()
    raw_root = within(project_root, project_root / dataset.paths.raw)
    interim_root = within(project_root, project_root / dataset.paths.interim)
    report_root = within(project_root, project_root / dataset.paths.reports)
    raw = raw_root / dataset.provider / dataset.revision
    canonical = (
        interim_root
        / dataset.provider
        / dataset.revision
        / (f"{dataset.competition_id}-{dataset.season_id}")
        / MAPPING_VERSION
    )
    report_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    report_path = report_root / "ingestion_runs" / f"{report_id}.json"
    errors = []
    canonical_artifacts = []
    results = []
    store = SnapshotStore(
        raw,
        dataset.revision,
        str(dataset.data_license_url),
        offline=offline,
        **({"fetcher": fetcher} if fetcher else {}),
    )
    report = {
        "phase": 2,
        "revision": dataset.revision,
        "mapping_version": MAPPING_VERSION,
        "started_at": datetime.now(UTC).isoformat(),
        "offline": offline,
        "data_validation": "canonical_shape_and_basic_identity_only",
        "minutes_validation": "not_run",
        "canonical_quality": "UNVALIDATED",
        "report_path": report_path.relative_to(project_root).as_posix(),
    }
    with cohort_lock(raw / ".ingestion.lock", project_root):
        provider = StatsBombOpenDataProvider(store, dataset)
        try:
            catalog = provider.list_competition_seasons()
            matches = provider.list_matches(
                make_id("statsbomb", "competition", dataset.competition_id),
                make_id("statsbomb", "season", dataset.season_id),
            )
            if len(matches) != dataset.expected_match_count:
                raise IngestionError("Audited match count does not match source")
            teams = {t for m in matches for t in (m.home_team_id, m.away_team_id)}
            if len(teams) != dataset.expected_team_count:
                raise IngestionError("Audited team count does not match source")
            selected = matches[:limit] if limit else matches
            report["requested_matches"] = len(selected)
            report["cohort_match_count"] = len(matches)
            canonical_artifacts.append(write_partition(canonical, "catalog", "all", catalog))
            canonical_artifacts.append(write_partition(canonical, "matches", "all", matches))

            def process(match):
                events = provider.load_events(match.match_id)
                lineups = provider.load_lineups(match.match_id)
                check_match_records(match, events, lineups)
                key = match.match_id.rsplit(":", 1)[1]
                artifacts = [
                    write_partition(canonical, "events", key, events),
                    write_partition(canonical, "lineups", key, lineups),
                ]
                flags = Counter(flag for e in events for flag in e.quality_flags)
                flags.update(
                    flag
                    for t in lineups
                    for p in t.entries
                    for ps in p.positions
                    for flag in ps.quality_flags
                )
                flags.update(
                    flag
                    for t in lineups
                    for p in t.entries
                    for c in p.cards
                    for flag in c.quality_flags
                )
                return {
                    "match_id": match.match_id,
                    "event_count": len(events),
                    "roster_entries": sum(len(t.entries) for t in lineups),
                    "card_observations": sum(len(p.cards) for t in lineups for p in t.entries),
                    "quality_flags": dict(flags),
                    "artifacts": artifacts,
                }

            with ThreadPoolExecutor(max_workers=workers) as pool:
                jobs = {pool.submit(process, match): match.match_id for match in selected}
                for completed, future in enumerate(as_completed(jobs), 1):
                    try:
                        result = future.result()
                        results.append(result)
                        canonical_artifacts.extend(result["artifacts"])
                    except Exception as error:
                        errors.append({"match_id": jobs[future], "error": str(error)})
                    if progress:
                        progress(completed, len(selected), len(errors))
            if errors:
                raise IngestionError(f"{len(errors)} match(es) failed; verified caches can resume")
            canonical_artifacts.sort(key=lambda a: (a["kind"], a["key"]))
            flags = Counter()
            for result in results:
                flags.update(result["quality_flags"])
            manifest = {
                "manifest_schema": "1.0",
                "mapping_version": MAPPING_VERSION,
                "provider": "statsbomb",
                "revision": dataset.revision,
                "competition_id": dataset.competition_id,
                "season_id": dataset.season_id,
                "cohort_match_count": len(matches),
                "ingested_match_count": len(results),
                "full_cohort": len(results) == len(matches),
                "canonical_quality": "UNVALIDATED",
                "source_artifacts": [a.model_dump(mode="json") for a in store.artifacts],
                "canonical_artifacts": canonical_artifacts,
                "event_count": sum(r["event_count"] for r in results),
                "roster_entries": sum(r["roster_entries"] for r in results),
                "card_observations": sum(r["card_observations"] for r in results),
                "quality_flags": dict(sorted(flags.items())),
            }
            manifest_data = json_bytes(manifest)
            manifest_id = digest(manifest_data)
            manifest_path = canonical / "manifests" / f"{manifest_id}.json"
            immutable_write(manifest_path, manifest_data, project_root)
            report.update(
                status="COMPLETE" if manifest["full_cohort"] else "PARTIAL",
                ingested_matches=len(results),
                event_count=manifest["event_count"],
                roster_entries=manifest["roster_entries"],
                quality_flags=manifest["quality_flags"],
                manifest_sha256=manifest_id,
                manifest_path=manifest_path.relative_to(project_root).as_posix(),
            )
        except Exception as error:
            report.update(status="FAILED", ingested_matches=len(results), error=str(error))
            if not errors:
                errors.append({"error": str(error)})
        report.update(store.stats)
        report["errors"] = errors
        report["finished_at"] = datetime.now(UTC).isoformat()
        immutable_write(report_path, json_bytes(report), project_root)
    return report
