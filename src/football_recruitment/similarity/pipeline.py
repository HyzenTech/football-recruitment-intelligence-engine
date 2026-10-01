"""Immutable similarity artifacts with complete replay from verified profiles."""

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
from football_recruitment.normalization.pipeline import verify_profiles
from football_recruitment.similarity.engine import SIMILARITY_VERSION, all_queries
from football_recruitment.similarity.evaluation import evaluate_similarity


def base_path(settings, project_root):
    d = settings.dataset
    return (
        within(project_root, project_root / d.paths.processed)
        / d.provider
        / d.revision
        / f"{d.competition_id}-{d.season_id}"
    )


def load_profiles(settings, project_root, profile_manifest):
    verified = verify_profiles(settings, project_root, profile_manifest)
    root = base_path(settings, project_root) / PROFILE_VERSION
    content = within(root, profile_manifest).read_bytes()
    if digest(content) != verified["profile_manifest_sha256"]:
        raise IngestionError("Profile input changed after verification")
    report = strict_json(content)
    artifact = next(a for a in report["artifacts"] if a["kind"] == "profiles")
    data = within(root, root / artifact["path"]).read_bytes()
    if digest(data) != artifact["sha256"]:
        raise IngestionError("Profile table changed after verification")
    return [strict_json(line) for line in data.splitlines()], report, verified


def summary(settings, verified, results):
    return {
        "phase": 6,
        "similarity_version": SIMILARITY_VERSION,
        "network_access": False,
        "source_profile_manifest_sha256": verified["profile_manifest_sha256"],
        "full_cohort": verified["full_cohort"],
        "similarity_settings": settings.similarity.model_dump(mode="json"),
        "query_count": len(results),
        "status_counts": dict(sorted(Counter(r["status"] for r in results).items())),
        "available_queries_by_role": dict(
            sorted(
                Counter(r["position_group"] for r in results if r["status"] == "AVAILABLE").items()
            )
        ),
        "neighbor_count": sum(len(r["neighbors"]) for r in results),
        "reference_selection": (
            "longest_eligible_spell_per_player_in_role_then_team_id; "
            "exclude_all_query_player_spells"
        ),
        "scaler_population": "complete_candidates_excluding_query_player",
        "minimum_peer_count": settings.cohorts.minimum_peer_count,
    }


def build_similarity(settings, project_root, profile_manifest):
    project_root = project_root.resolve()
    profiles, _, verified = load_profiles(settings, project_root, profile_manifest)
    results = all_queries(profiles, settings)
    root = base_path(settings, project_root) / SIMILARITY_VERSION
    with cohort_lock(root / ".similarity.lock", project_root):
        data = b"".join(json_bytes(r) for r in results)
        sha = digest(data)
        path = f"queries/{sha}.jsonl"
        immutable_write(root / path, data, root)
        evaluation = json_bytes(evaluate_similarity(profiles, settings, results))
        evaluation_sha = digest(evaluation)
        evaluation_path = f"evaluation/{evaluation_sha}.json"
        immutable_write(root / evaluation_path, evaluation, root)
        report = summary(settings, verified, results) | {
            "artifacts": [
                {
                    "kind": "queries",
                    "path": path,
                    "sha256": sha,
                    "byte_count": len(data),
                    "record_count": len(results),
                }
            ]
        }
        report["artifacts"].append(
            {
                "kind": "evaluation",
                "path": evaluation_path,
                "sha256": evaluation_sha,
                "byte_count": len(evaluation),
                "record_count": 1,
            }
        )
        content = json_bytes(report)
        sha = digest(content)
        manifest = root / "manifests" / f"{sha}.json"
        immutable_write(manifest, content, root)
    return {k: v for k, v in report.items() if k not in {"artifacts", "similarity_settings"}} | {
        "similarity_manifest_sha256": sha,
        "similarity_manifest_path": manifest.relative_to(project_root).as_posix(),
    }


def verify_similarity(settings, project_root, manifest_path):
    project_root = project_root.resolve()
    base = base_path(settings, project_root)
    root = base / SIMILARITY_VERSION
    content = within(root, manifest_path).read_bytes()
    report = strict_json(content)
    if digest(content) != manifest_path.stem or report["similarity_version"] != SIMILARITY_VERSION:
        raise IngestionError("Similarity manifest checksum/version mismatch")
    source = (
        base / PROFILE_VERSION / "manifests" / (report["source_profile_manifest_sha256"] + ".json")
    )
    profiles, _, verified = load_profiles(settings, project_root, source)
    results = all_queries(profiles, settings)
    expected = summary(settings, verified, results)
    if {k: v for k, v in report.items() if k != "artifacts"} != expected:
        raise IngestionError("Similarity report/configuration differs from replay")
    expected_tables = {
        "queries": (b"".join(json_bytes(r) for r in results), len(results)),
        "evaluation": (json_bytes(evaluate_similarity(profiles, settings, results)), 1),
    }
    seen = set()
    for artifact in report["artifacts"]:
        kind = artifact["kind"]
        if kind not in expected_tables or kind in seen:
            raise IngestionError("Unexpected similarity partition")
        seen.add(kind)
        expected_data, count = expected_tables[kind]
        data = within(root, root / artifact["path"]).read_bytes()
        if (
            data != expected_data
            or digest(data) != artifact["sha256"]
            or len(data) != artifact["byte_count"]
            or count != artifact["record_count"]
        ):
            raise IngestionError("Similarity artifact fails integrity/replay verification")
    if seen != set(expected_tables):
        raise IngestionError("Missing similarity partition")
    return {
        "status": "VERIFIED",
        "query_count": len(results),
        "similarity_manifest_sha256": digest(content),
        "replayed_from_verified_profiles": True,
    }
