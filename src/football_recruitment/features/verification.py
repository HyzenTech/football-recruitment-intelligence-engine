"""Offline feature integrity, exposure census, aggregation and derived-value checks."""

from collections import defaultdict

from football_recruitment.features.metrics import (
    FEATURE_VERSION,
    METRICS,
    Statistic,
    aggregate_statistics,
    values,
)
from football_recruitment.ingestion.storage import IngestionError, digest, strict_json, within
from football_recruitment.preprocessing.minutes import MINUTES_VERSION
from football_recruitment.validation.verification import verify_minutes


def verify_features(settings, project_root, manifest_path):
    project_root = project_root.resolve()
    d = settings.dataset
    base = (
        within(project_root, project_root / d.paths.processed)
        / d.provider
        / d.revision
        / (f"{d.competition_id}-{d.season_id}")
    )
    root = base / FEATURE_VERSION
    path = within(root, manifest_path)
    content = path.read_bytes()
    report = strict_json(content)
    if digest(content) != path.stem or report["feature_version"] != FEATURE_VERSION:
        raise IngestionError("Feature manifest checksum/version mismatch")
    minutes_path = (
        base
        / MINUTES_VERSION
        / "manifests"
        / (report["upstream_minutes_manifest_sha256"] + ".json")
    )
    upstream_result = verify_minutes(settings, project_root, minutes_path)
    upstream = strict_json(minutes_path.read_bytes())
    exposure = {}
    for a in upstream["artifacts"]:
        if a["kind"] == "appearances":
            for row in map(
                strict_json,
                within(base / MINUTES_VERSION, base / MINUTES_VERSION / a["path"])
                .read_bytes()
                .splitlines(),
            ):
                if row["quality_status"] == "VALIDATED":
                    exposure[row["match_id"], row["player_id"], row["team_id"]] = row
    tables = {}
    for a in report["artifacts"]:
        if a["kind"] not in {"player_match", "player_team_season"} or a["kind"] in tables:
            raise IngestionError("Invalid feature table partition")
        data = within(root, root / a["path"]).read_bytes()
        if digest(data) != a["sha256"] or len(data) != a["byte_count"]:
            raise IngestionError("Feature table checksum mismatch")
        rows = [strict_json(line) for line in data.splitlines()]
        if len(rows) != a["record_count"]:
            raise IngestionError("Feature table row count mismatch")
        tables[a["kind"]] = rows
    if set(tables) != {"player_match", "player_team_season"}:
        raise IngestionError("Feature table missing")
    groups = defaultdict(list)
    seen = set()
    for row in tables["player_match"]:
        key = row["match_id"], row["player_id"], row["team_id"]
        if key in seen or key not in exposure:
            raise IngestionError("Duplicate or unvalidated player-match feature row")
        seen.add(key)
        for field in ("playing_seconds", "nominal_minutes"):
            if row[field] != exposure[key][field]:
                raise IngestionError("Feature exposure differs from validated minutes")
        groups[row["player_id"], row["team_id"]].append(row)
    if seen != set(exposure):
        raise IngestionError("Validated appearance missing from feature table")
    season_seen = set()
    for row in tables["player_team_season"]:
        key = row["player_id"], row["team_id"]
        if key in season_seen or key not in groups:
            raise IngestionError("Duplicate or foreign player-team-season feature row")
        season_seen.add(key)
        source = groups[key]
        for field in ("playing_seconds", "nominal_minutes", "appearances", "starts"):
            if abs(row[field] - sum(r[field] for r in source)) > 1e-6:
                raise IngestionError("Season exposure aggregation mismatch")
        expected = aggregate_statistics(
            [{k: Statistic.model_validate(v) for k, v in r["statistics"].items()} for r in source]
        )
        if row["statistics"] != {k: v.model_dump(mode="json") for k, v in expected.items()}:
            raise IngestionError("Season sufficient-statistics aggregation mismatch")
    if season_seen != set(groups):
        raise IngestionError("Player-team-season coverage mismatch")
    for rows in tables.values():
        for row in rows:
            if set(row["statistics"]) != set(METRICS) or row["feature_version"] != FEATURE_VERSION:
                raise IngestionError("Unexpected feature definitions")
            statistics = {k: Statistic.model_validate(v) for k, v in row["statistics"].items()}
            if any(s.missing > s.samples for s in statistics.values()):
                raise IngestionError("Impossible feature missingness")
            minutes = (
                row["playing_seconds"] / 60
                if report["minutes_convention"] == "elapsed_including_stoppage"
                else row["nominal_minutes"]
            )
            if row["denominator_minutes"] != minutes or row["values"] != values(
                statistics, minutes
            ):
                raise IngestionError("Feature values/rates differ from declared statistics")
            if row["minimum_minutes_met"] != (minutes >= report["minimum_minutes"]):
                raise IngestionError("Feature minute eligibility mismatch")
    if (
        len(tables["player_match"]) != report["player_match_rows"]
        or len(tables["player_team_season"]) != report["player_team_season_rows"]
    ):
        raise IngestionError("Feature report census mismatch")
    return {
        "phase": 4,
        "feature_integrity": "VERIFIED",
        "network_access": False,
        "full_cohort": upstream_result["full_cohort"],
        "feature_manifest_sha256": digest(content),
        "player_match_rows": len(tables["player_match"]),
        "player_team_season_rows": len(tables["player_team_season"]),
        "metric_count": len(METRICS),
    }
