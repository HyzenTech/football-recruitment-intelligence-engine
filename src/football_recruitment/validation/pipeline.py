"""Validate every ingested match and publish explicit usable/quarantined outputs."""

from collections import Counter
from pathlib import Path

from football_recruitment.domain.models import Event, Match, TeamLineup
from football_recruitment.ingestion.pipeline import write_partition
from football_recruitment.ingestion.storage import (
    IngestionError,
    cohort_lock,
    digest,
    immutable_write,
    json_bytes,
    strict_json,
    within,
)
from football_recruitment.ingestion.verification import verify_manifest
from football_recruitment.preprocessing.minutes import (
    CLOCK_TOLERANCE,
    MINUTES_VERSION,
    reconcile_match,
)
from football_recruitment.providers.statsbomb import MAPPING_VERSION


def validate_cohort(settings, project_root: Path, manifest_path: Path, *, progress=None):
    """Offline only; corrupted input fails before any usable processed output is published."""
    project_root = project_root.resolve()
    integrity = verify_manifest(settings, project_root, manifest_path)
    source = strict_json(manifest_path.read_bytes())
    dataset = settings.dataset
    canonical = (
        within(project_root, project_root / dataset.paths.interim)
        / dataset.provider
        / (dataset.revision)
        / f"{dataset.competition_id}-{dataset.season_id}"
        / MAPPING_VERSION
    )
    processed = (
        within(project_root, project_root / dataset.paths.processed)
        / dataset.provider
        / (dataset.revision)
        / f"{dataset.competition_id}-{dataset.season_id}"
        / MINUTES_VERSION
    )
    reports = within(project_root, project_root / dataset.paths.reports) / "validation"
    artifacts = {(a["kind"], a["key"]): a for a in source["canonical_artifacts"]}

    def load(kind, key, model):
        artifact = artifacts[kind, key]
        path = within(canonical, canonical / artifact["path"])
        data = path.read_bytes()
        if digest(data) != artifact["sha256"]:
            raise IngestionError("Input changed after verification")
        return [model.model_validate_json(line) for line in data.splitlines() if line.strip()]

    matches = load("matches", "all", Match)
    keys = {key for kind, key in artifacts if kind == "events"}
    if len({m.match_id for m in matches}) != len(matches):
        raise IngestionError("Duplicate canonical match IDs")
    if not keys <= {m.match_id.rsplit(":", 1)[1] for m in matches}:
        raise IngestionError("Event partition is absent from canonical match metadata")
    selected = sorted(
        (m for m in matches if m.match_id.rsplit(":", 1)[1] in keys), key=lambda m: m.match_id
    )
    counts = Counter({"VALIDATED": 0, "NEEDS_REVIEW": 0, "EXCLUDED": 0, "unused_roster": 0})
    flags = Counter()
    source_flags = Counter()
    match_reports = []
    partitions = []
    event_ids = set()
    elapsed_seconds = nominal_minutes = 0.0
    with cohort_lock(processed / ".validation.lock", project_root):
        for i, match in enumerate(selected, 1):
            key = match.match_id.rsplit(":", 1)[1]
            events = load("events", key, Event)
            if event_ids.intersection(e.event_id for e in events):
                raise IngestionError("Event ID collision across matches")
            event_ids.update(e.event_id for e in events)
            source_flags.update(flag for event in events for flag in event.quality_flags)
            lineups = load("lineups", key, TeamLineup)
            result = reconcile_match(
                match,
                events,
                lineups,
                settings.cohorts.position_groups,
                settings.cohorts.role_mapping_version,
            )
            if len(result.appearances) + len(result.unused_roster) != sum(
                len(t.entries) for t in lineups
            ):
                raise IngestionError(f"Roster reconciliation failed for {match.match_id}")
            for appearance in result.appearances:
                counts[appearance.quality_status.value] += 1
                if appearance.playing_seconds is not None:
                    elapsed_seconds += appearance.playing_seconds
                    nominal_minutes += appearance.nominal_minutes
            counts["unused_roster"] += len(result.unused_roster)
            flags.update(issue["code"] for issue in result.issues)
            for kind, records in (
                ("periods", result.periods),
                ("appearances", result.appearances),
                ("presence", result.presence),
                ("positions", result.positions),
            ):
                partitions.append(write_partition(processed, kind, key, records))
            match_reports.append(
                {
                    "match_id": match.match_id,
                    "appearance_quality": dict(
                        sorted(Counter(a.quality_status.value for a in result.appearances).items())
                    ),
                    "issues": result.issues,
                    "unused_roster": result.unused_roster,
                }
            )
            if progress:
                progress(i, len(selected))
        partitions.sort(key=lambda a: (a["kind"], a["key"]))
        report = {
            "phase": 3,
            "validation_version": MINUTES_VERSION,
            "source_manifest_sha256": integrity["manifest_sha256"],
            "revision": dataset.revision,
            "network_access": False,
            "full_cohort": source["full_cohort"],
            "matches_checked": len(selected),
            "status": (
                ("COMPLETE" if source["full_cohort"] else "PARTIAL")
                + ("_WITH_EXCLUSIONS" if counts["NEEDS_REVIEW"] else "")
            ),
            "minutes_convention": "elapsed_including_stoppage",
            "nominal_minutes_convention": "per_period_intersection_with_nominal_window",
            "position_clock_tolerance_seconds": CLOCK_TOLERANCE,
            "appearance_quality": dict(sorted(counts.items())),
            "validated_playing_seconds": round(elapsed_seconds, 6),
            "validated_nominal_minutes": round(nominal_minutes, 6),
            "issue_counts": dict(sorted(flags.items())),
            "event_mapping_warning_counts": dict(sorted(source_flags.items())),
            "role_mapping": settings.cohorts.model_dump(mode="json"),
            "matches": match_reports,
            "scope": "appearance_and_position_minutes; feature eligibility remains pending",
        }
        report_data = json_bytes(report)
        report_sha = digest(report_data)
        report_path = reports / f"{report_sha}.json"
        immutable_write(report_path, report_data, project_root)
        manifest = {
            "schema_version": "1.0",
            "validation_version": MINUTES_VERSION,
            "source_manifest_sha256": integrity["manifest_sha256"],
            "validation_report_sha256": report_sha,
            "validation_report_path": report_path.relative_to(project_root).as_posix(),
            "full_cohort": source["full_cohort"],
            "revision": dataset.revision,
            "appearance_quality": report["appearance_quality"],
            "artifacts": partitions,
        }
        content = json_bytes(manifest)
        manifest_sha = digest(content)
        processed_manifest = processed / "manifests" / f"{manifest_sha}.json"
        immutable_write(processed_manifest, content, project_root)
        return {k: v for k, v in report.items() if k not in ("matches", "role_mapping")} | {
            "validation_report_path": report_path.relative_to(project_root).as_posix(),
            "validation_manifest_path": processed_manifest.relative_to(project_root).as_posix(),
            "validation_manifest_sha256": manifest_sha,
        }
