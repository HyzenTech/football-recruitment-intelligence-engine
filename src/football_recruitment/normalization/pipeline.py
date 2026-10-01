"""Versioned offline profiles with replay verification and positional lineage."""

from collections import Counter, defaultdict

from football_recruitment.domain.models import PositionInterval
from football_recruitment.features.metrics import FEATURE_VERSION
from football_recruitment.features.verification import verify_features
from football_recruitment.ingestion.storage import (
    IngestionError,
    cohort_lock,
    digest,
    immutable_write,
    json_bytes,
    strict_json,
    within,
)
from football_recruitment.normalization.engine import PROFILE_VERSION, build_profiles
from football_recruitment.preprocessing.minutes import MINUTES_VERSION


def inputs(settings, project_root, feature_manifest):
    verified = verify_features(settings, project_root, feature_manifest)
    d = settings.dataset
    base = (
        within(project_root, project_root / d.paths.processed)
        / d.provider
        / d.revision
        / f"{d.competition_id}-{d.season_id}"
    )
    feature_root = base / FEATURE_VERSION
    source = strict_json(within(feature_root, feature_manifest).read_bytes())
    if source["full_cohort"] != verified["full_cohort"]:
        raise IngestionError("Feature cohort completeness differs from verified minutes")
    if source["minutes_convention"] != settings.cohorts.minutes_convention:
        raise IngestionError("Feature and profile denominator conventions differ")
    minutes_root = base / MINUTES_VERSION
    upstream = strict_json(
        (
            minutes_root / "manifests" / (source["upstream_minutes_manifest_sha256"] + ".json")
        ).read_bytes()
    )
    roles = defaultdict(lambda: defaultdict(float))
    excluded = Counter()
    mapping = {
        position: group.value
        for group, ids in settings.cohorts.position_groups.items()
        for position in ids
    }

    def records(root, artifact):
        data = within(root, root / artifact["path"]).read_bytes()
        if digest(data) != artifact["sha256"] or len(data) != artifact["byte_count"]:
            raise IngestionError("Profile input changed after verification")
        return [strict_json(line) for line in data.splitlines()]

    for artifact in upstream["artifacts"]:
        if artifact["kind"] == "positions":
            for row in records(minutes_root, artifact):
                interval = PositionInterval.model_validate(row)
                if (
                    interval.mapping_version != settings.cohorts.role_mapping_version
                    or mapping[interval.source_position_id] != interval.position_group.value
                ):
                    raise IngestionError("Position mapping differs from configured cohort mapping")
                roles[interval.player_id, interval.team_id][interval.position_group.value] += (
                    interval.end.elapsed_seconds - interval.start.elapsed_seconds
                )
        elif artifact["kind"] == "appearances":
            for row in records(minutes_root, artifact):
                if row["quality_status"] != "VALIDATED":
                    excluded[row["player_id"], row["team_id"]] += 1
    artifact = next(a for a in source["artifacts"] if a["kind"] == "player_team_season")
    rows = records(feature_root, artifact)
    for row in rows:
        if (
            row["competition_id"] != f"{d.provider}:competition:{d.competition_id}"
            or row["season_id"] != f"{d.provider}:season:{d.season_id}"
        ):
            raise IngestionError("Feature row belongs to a different comparison cohort")
        count = excluded[row["player_id"], row["team_id"]]
        if row["excluded_appearances"] != count or row["partial_player_season"] != bool(
            count or not source["full_cohort"]
        ):
            raise IngestionError("Partial season flags disagree with validated appearances")
    profiles, references = build_profiles(rows, roles, settings)
    return base, source, verified, profiles, references


def build_profile_artifacts(settings, project_root, feature_manifest):
    project_root = project_root.resolve()
    base, source, verified, profiles, references = inputs(settings, project_root, feature_manifest)
    root = base / PROFILE_VERSION
    with cohort_lock(root / ".profiles.lock", project_root):
        artifacts = []
        for kind, data, count in (
            ("profiles", b"".join(json_bytes(p) for p in profiles), len(profiles)),
            ("references", json_bytes(references), len(references)),
        ):
            sha = digest(data)
            path = f"{kind}/{sha}.{'jsonl' if kind == 'profiles' else 'json'}"
            immutable_write(root / path, data, root)
            artifacts.append(
                dict(kind=kind, path=path, sha256=sha, byte_count=len(data), record_count=count)
            )
        report = {
            "phase": 5,
            "profile_version": PROFILE_VERSION,
            "network_access": False,
            "source_feature_manifest_sha256": digest(feature_manifest.read_bytes()),
            "source_manifest_sha256": source["source_manifest_sha256"],
            "full_cohort": verified["full_cohort"],
            "profile_count": len(profiles),
            "eligible_profile_count": sum(p["peer_eligible"] for p in profiles),
            "eligible_profiles_by_role": dict(
                sorted(
                    Counter(
                        p["primary_position_group"] for p in profiles if p["peer_eligible"]
                    ).items()
                )
            ),
            "eligibility_reason_counts": dict(
                sorted(Counter(r for p in profiles for r in p["eligibility_reasons"]).items())
            ),
            "metric_status_counts": dict(
                sorted(
                    Counter(v["status"] for p in profiles for v in p["metrics"].values()).items()
                )
            ),
            "category_status_counts": dict(
                sorted(
                    Counter(v["status"] for p in profiles for v in p["categories"].values()).items()
                )
            ),
            "cohort_settings": settings.cohorts.model_dump(mode="json"),
            "reference_selection": "longest_eligible_team_spell_per_player_per_role_then_team_id",
            "percentile_formula": (
                "100*(count_less+0.5*count_equal)/n; lower direction uses 100-result"
            ),
            "partial_season_policy": "exclude_from_peers",
            "artifacts": artifacts,
        }
        data = json_bytes(report)
        sha = digest(data)
        path = root / "manifests" / f"{sha}.json"
        immutable_write(path, data, root)
    return {k: v for k, v in report.items() if k not in {"artifacts", "cohort_settings"}} | {
        "profile_manifest_sha256": sha,
        "profile_manifest_path": path.relative_to(project_root).as_posix(),
    }


def verify_profiles(settings, project_root, manifest_path):
    project_root = project_root.resolve()
    d = settings.dataset
    base = (
        within(project_root, project_root / d.paths.processed)
        / d.provider
        / d.revision
        / f"{d.competition_id}-{d.season_id}"
    )
    root = base / PROFILE_VERSION
    data = within(root, manifest_path).read_bytes()
    report = strict_json(data)
    if digest(data) != manifest_path.stem or report["profile_version"] != PROFILE_VERSION:
        raise IngestionError("Profile manifest checksum/version mismatch")
    if report["cohort_settings"] != settings.cohorts.model_dump(mode="json"):
        raise IngestionError("Profile cohort settings differ from current settings")
    source_path = (
        base / FEATURE_VERSION / "manifests" / (report["source_feature_manifest_sha256"] + ".json")
    )
    _, source, verified, profiles, references = inputs(settings, project_root, source_path)
    expected = {
        "profiles": (b"".join(json_bytes(p) for p in profiles), len(profiles)),
        "references": (json_bytes(references), len(references)),
    }
    seen = set()
    for artifact in report["artifacts"]:
        kind = artifact["kind"]
        if kind not in expected or kind in seen:
            raise IngestionError("Unexpected profile partition")
        seen.add(kind)
        content = within(root, root / artifact["path"]).read_bytes()
        replay, count = expected[kind]
        if (
            content != replay
            or digest(content) != artifact["sha256"]
            or len(content) != artifact["byte_count"]
            or count != artifact["record_count"]
        ):
            raise IngestionError("Profile artifacts fail integrity/replay verification")
    if (
        seen != set(expected)
        or report["profile_count"] != len(profiles)
        or report["source_manifest_sha256"] != source["source_manifest_sha256"]
        or report["full_cohort"] != verified["full_cohort"]
    ):
        raise IngestionError("Profile manifest census/lineage mismatch")
    if report["eligible_profile_count"] != sum(p["peer_eligible"] for p in profiles):
        raise IngestionError("Profile eligibility census mismatch")
    for field, actual in (
        (
            "eligible_profiles_by_role",
            Counter(p["primary_position_group"] for p in profiles if p["peer_eligible"]),
        ),
        (
            "eligibility_reason_counts",
            Counter(r for p in profiles for r in p["eligibility_reasons"]),
        ),
        (
            "metric_status_counts",
            Counter(v["status"] for p in profiles for v in p["metrics"].values()),
        ),
        (
            "category_status_counts",
            Counter(v["status"] for p in profiles for v in p["categories"].values()),
        ),
    ):
        if report[field] != dict(actual):
            raise IngestionError("Profile report counts differ from replay")
    return {
        "status": "VERIFIED",
        "profile_count": len(profiles),
        "reference_set_count": len(references),
        "full_cohort": verified["full_cohort"],
        "profile_manifest_sha256": digest(data),
        "replayed_from_verified_features_and_positions": True,
    }
