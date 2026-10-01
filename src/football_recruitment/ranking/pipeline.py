"""Versioned recruitment artifacts with full replay from verified profiles."""

from collections import Counter

from football_recruitment.ingestion.storage import (
    IngestionError,
    cohort_lock,
    digest,
    immutable_write,
    json_bytes,
    strict_json,
    within,
)
from football_recruitment.normalization.engine import PROFILE_VERSION
from football_recruitment.ranking.engine import RANKING_VERSION, build_rankings, evaluate_rankings
from football_recruitment.similarity.pipeline import base_path, load_profiles


def summary(settings, verified, rankings):
    return {
        "phase": 7,
        "ranking_version": RANKING_VERSION,
        "network_access": False,
        "source_profile_manifest_sha256": verified["profile_manifest_sha256"],
        "full_cohort": verified["full_cohort"],
        "ranking_settings": settings.ranking.model_dump(mode="json"),
        "requirement_count": len(rankings),
        "status_counts": dict(sorted(Counter(r["status"] for r in rankings.values()).items())),
        "returned_candidate_count": sum(len(r["rankings"]) for r in rankings.values()),
        "minimum_peer_count": settings.cohorts.minimum_peer_count,
    }


def contents(profiles, settings):
    rankings = build_rankings(profiles, settings)
    return rankings, {
        "rankings": json_bytes(rankings),
        "evaluation": json_bytes(evaluate_rankings(profiles, settings, rankings)),
    }


def build_ranking_artifacts(settings, project_root, profile_manifest):
    project_root = project_root.resolve()
    profiles, _, verified = load_profiles(settings, project_root, profile_manifest)
    rankings, tables = contents(profiles, settings)
    root = base_path(settings, project_root) / RANKING_VERSION
    with cohort_lock(root / ".ranking.lock", project_root):
        artifacts = []
        for kind, data in tables.items():
            sha = digest(data)
            path = f"{kind}/{sha}.json"
            immutable_write(root / path, data, root)
            artifacts.append(
                {
                    "kind": kind,
                    "path": path,
                    "sha256": sha,
                    "byte_count": len(data),
                    "record_count": 1,
                }
            )
        report = summary(settings, verified, rankings) | {"artifacts": artifacts}
        data = json_bytes(report)
        sha = digest(data)
        path = root / "manifests" / f"{sha}.json"
        immutable_write(path, data, root)
    return {k: v for k, v in report.items() if k not in {"ranking_settings", "artifacts"}} | {
        "ranking_manifest_sha256": sha,
        "ranking_manifest_path": path.relative_to(project_root).as_posix(),
    }


def verify_rankings(settings, project_root, manifest_path):
    project_root = project_root.resolve()
    base = base_path(settings, project_root)
    root = base / RANKING_VERSION
    data = within(root, manifest_path).read_bytes()
    report = strict_json(data)
    if digest(data) != manifest_path.stem or report["ranking_version"] != RANKING_VERSION:
        raise IngestionError("Ranking manifest checksum/version mismatch")
    source = (
        base / PROFILE_VERSION / "manifests" / (report["source_profile_manifest_sha256"] + ".json")
    )
    profiles, _, verified = load_profiles(settings, project_root, source)
    rankings, tables = contents(profiles, settings)
    if {k: v for k, v in report.items() if k != "artifacts"} != summary(
        settings, verified, rankings
    ):
        raise IngestionError("Ranking configuration/report differs from replay")
    seen = set()
    for artifact in report["artifacts"]:
        kind = artifact["kind"]
        if kind not in tables or kind in seen:
            raise IngestionError("Unexpected ranking partition")
        seen.add(kind)
        content = within(root, root / artifact["path"]).read_bytes()
        if (
            content != tables[kind]
            or digest(content) != artifact["sha256"]
            or len(content) != artifact["byte_count"]
            or artifact["record_count"] != 1
        ):
            raise IngestionError("Ranking artifact fails integrity/replay verification")
    if seen != set(tables):
        raise IngestionError("Missing ranking partition")
    return {
        "status": "VERIFIED",
        "ranking_manifest_sha256": digest(data),
        "requirement_count": len(rankings),
        "replayed_from_verified_profiles": True,
    }
