"""Offline canonical events -> player-match -> player-team-season sufficient statistics."""

from collections import Counter, defaultdict
from pathlib import Path

from football_recruitment.domain.models import Appearance, Event, Match, QualityStatus, TeamLineup
from football_recruitment.features.metrics import (
    ADMIN,
    FEATURE_VERSION,
    METRICS,
    Statistic,
    accumulate_event,
    aggregate_statistics,
    empty_statistics,
    values,
)
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
from football_recruitment.preprocessing.minutes import MINUTES_VERSION
from football_recruitment.providers.statsbomb import MAPPING_VERSION
from football_recruitment.validation.verification import verify_minutes


def build_features(settings, project_root: Path, minutes_manifest: Path, *, progress=None):
    project_root = project_root.resolve()
    if settings.metrics.definition_version != FEATURE_VERSION:
        raise IngestionError("Metric definitions must match the implemented feature version")
    verified = verify_minutes(settings, project_root, minutes_manifest)
    upstream = strict_json(minutes_manifest.read_bytes())
    dataset = settings.dataset
    tail = (
        Path(dataset.provider) / dataset.revision / f"{dataset.competition_id}-{dataset.season_id}"
    )
    canonical = within(project_root, project_root / dataset.paths.interim) / tail / MAPPING_VERSION
    minutes_root = (
        within(project_root, project_root / dataset.paths.processed) / tail / MINUTES_VERSION
    )
    source_path = canonical / "manifests" / (upstream["source_manifest_sha256"] + ".json")
    verify_manifest(settings, project_root, source_path)
    source = strict_json(source_path.read_bytes())
    source_parts = {(a["kind"], a["key"]): a for a in source["canonical_artifacts"]}
    minutes_parts = {(a["kind"], a["key"]): a for a in upstream["artifacts"]}

    def load(root, artifact, model):
        data = within(root, root / artifact["path"]).read_bytes()
        if digest(data) != artifact["sha256"]:
            raise IngestionError("Feature input changed after verification")
        return [model.model_validate_json(line) for line in data.splitlines() if line.strip()]

    match_metadata = {
        m.match_id.rsplit(":", 1)[1]: m
        for m in load(canonical, source_parts["matches", "all"], Match)
    }
    output = within(project_root, project_root / dataset.paths.processed) / tail / FEATURE_VERSION
    rows = []
    excluded = Counter()
    event_counts = Counter()
    issues = []
    season_groups = defaultdict(list)
    with cohort_lock(output / ".features.lock", project_root):
        keys = sorted(key for kind, key in minutes_parts if kind == "appearances")
        for i, key in enumerate(keys, 1):
            match = match_metadata[key]
            appearances = load(minutes_root, minutes_parts["appearances", key], Appearance)
            valid = {
                a.player_id: a for a in appearances if a.quality_status == QualityStatus.VALIDATED
            }
            for a in appearances:
                if a.quality_status != QualityStatus.VALIDATED:
                    excluded[a.player_id, a.team_id] += 1
            events = load(canonical, source_parts["events", key], Event)
            lineups = load(canonical, source_parts["lineups", key], TeamLineup)
            metadata = {
                p.player.player_id: (p.player.player_name, t.team.team_name)
                for t in lineups
                for p in t.entries
            }
            presence_data = within(
                minutes_root, minutes_root / minutes_parts["presence", key]["path"]
            ).read_bytes()
            if digest(presence_data) != minutes_parts["presence", key]["sha256"]:
                raise IngestionError("Presence changed after verification")
            presence = defaultdict(list)
            for interval in map(strict_json, presence_data.splitlines()):
                presence[interval["player_id"]].append(
                    (
                        interval["start"]["period"],
                        interval["start"]["elapsed_seconds"],
                        interval["end"]["elapsed_seconds"],
                    )
                )
            eligible = []
            for e in events:
                if e.period == 5:
                    event_counts["shootout"] += 1
                elif e.event_type in ADMIN:
                    event_counts["administrative"] += 1
                elif e.player_id not in valid:
                    event_counts["no_validated_appearance"] += 1
                elif e.team_id != valid[e.player_id].team_id or not any(
                    p == e.period and a - 1e-6 <= e.elapsed_seconds <= b + 1e-6
                    for p, a, b in presence[e.player_id]
                ):
                    raise IngestionError("Action outside validated presence reached feature stage")
                elif set(e.quality_flags) - {"UNMAPPED_PASS_OUTCOME"}:
                    raise IngestionError("Unreviewed event schema reached feature stage")
                else:
                    eligible.append(e)
                    event_counts["included"] += 1
            lookup = {e.event_id: e for e in events}
            eligible_shots = {e.event_id for e in eligible if e.event_type == "Shot"}
            used_shots = set()
            statistics = {player: empty_statistics() for player in valid}
            for event in sorted(eligible, key=lambda e: e.index):
                accumulate_event(
                    statistics[event.player_id],
                    event,
                    settings.metrics,
                    lookup,
                    eligible_shots,
                    used_shots,
                    issues,
                )
            for player, a in sorted(valid.items()):
                name, team_name = metadata[player]
                row = {
                    "match_id": a.match_id,
                    "competition_id": match.competition_id,
                    "season_id": match.season_id,
                    "player_id": player,
                    "team_id": a.team_id,
                    "player_name": name,
                    "team_name": team_name,
                    "appearances": 1,
                    "starts": int(a.starter),
                    "playing_seconds": a.playing_seconds,
                    "nominal_minutes": a.nominal_minutes,
                    "statistics": {
                        k: v.model_dump(mode="json") for k, v in statistics[player].items()
                    },
                }
                rows.append(row)
                season_groups[player, a.team_id].append(row)
            if progress:
                progress(i, len(keys))
        denominator = settings.cohorts.minutes_convention

        def finish(row):
            minutes = (
                row["playing_seconds"] / 60
                if denominator == "elapsed_including_stoppage"
                else row["nominal_minutes"]
            )
            row["denominator_minutes"] = minutes
            row["minutes_convention"] = denominator
            row["feature_version"] = FEATURE_VERSION
            row["values"] = values(
                {k: Statistic.model_validate(v) for k, v in row["statistics"].items()}, minutes
            )
            row["minimum_minutes_met"] = minutes >= settings.cohorts.minimum_minutes
            return row

        seasons = []
        for (player, team), group in sorted(season_groups.items()):
            row = {k: v for k, v in group[0].items() if k not in ("match_id", "statistics")}
            for k in ("playing_seconds", "nominal_minutes", "appearances", "starts"):
                row[k] = sum(r[k] for r in group)
            row["excluded_appearances"] = excluded[player, team]
            row["partial_player_season"] = bool(
                row["excluded_appearances"] or not verified["full_cohort"]
            )
            row["statistics"] = {
                k: v.model_dump(mode="json")
                for k, v in aggregate_statistics(
                    [
                        {k: Statistic.model_validate(v) for k, v in r["statistics"].items()}
                        for r in group
                    ]
                ).items()
            }
            seasons.append(finish(row))
        rows = [finish(row) for row in rows]
        artifacts = []
        for kind, records in (("player_match", rows), ("player_team_season", seasons)):
            data = b"".join(json_bytes(r) for r in records)
            sha = digest(data)
            path = f"{kind}/{sha}.jsonl"
            immutable_write(output / path, data, output)
            artifacts.append(
                {
                    "kind": kind,
                    "path": path,
                    "sha256": sha,
                    "byte_count": len(data),
                    "record_count": len(records),
                }
            )
        report = {
            "phase": 4,
            "feature_version": FEATURE_VERSION,
            "network_access": False,
            "full_cohort": verified["full_cohort"],
            "matches_checked": len(keys),
            "player_match_rows": len(rows),
            "player_team_season_rows": len(seasons),
            "unique_players": len({r["player_id"] for r in seasons}),
            "metric_count": len(METRICS),
            "event_disposition": dict(sorted(event_counts.items())),
            "quarantined_appearances": sum(excluded.values()),
            "partial_player_seasons": sum(r["partial_player_season"] for r in seasons),
            "metric_missing_player_seasons": {
                k: sum(r["statistics"][k]["missing"] > 0 for r in seasons) for k in METRICS
            },
            "issue_counts": dict(Counter(i["code"] for i in issues)),
            "issues": issues,
            "minutes_convention": denominator,
            "upstream_minutes_manifest_sha256": verified["validation_manifest_sha256"],
            "source_manifest_sha256": upstream["source_manifest_sha256"],
            "metric_settings": settings.metrics.model_dump(mode="json"),
            "minimum_minutes": settings.cohorts.minimum_minutes,
            "artifacts": artifacts,
        }
        data = json_bytes(report)
        sha = digest(data)
        path = output / "manifests" / f"{sha}.json"
        immutable_write(path, data, output)
        return {
            k: v for k, v in report.items() if k not in ("issues", "metric_settings", "artifacts")
        } | {
            "feature_manifest_sha256": sha,
            "feature_manifest_path": path.relative_to(project_root).as_posix(),
        }
