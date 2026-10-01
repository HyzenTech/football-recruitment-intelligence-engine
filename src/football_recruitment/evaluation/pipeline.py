"""Immutable combined evaluation and full replay verification."""

from football_recruitment.evaluation.engine import EVALUATION_VERSION, evaluate_cohort
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
from football_recruitment.similarity.pipeline import base_path, load_profiles


def summary(settings, verified, report):
    return {
        "phase": 8,
        "evaluation_version": EVALUATION_VERSION,
        "network_access": False,
        "source_profile_manifest_sha256": verified["profile_manifest_sha256"],
        "full_cohort": verified["full_cohort"],
        "settings": settings.model_dump(mode="json"),
        "replicates": report["replicates"],
        "combined_checks": report["combined_checks"],
        "similarity_attempts": len(report["similarity_records"]),
        "ranking_attempts": len(report["ranking_records"]),
        "football_review_status": report["football_review"]["status"],
        "external_archetype_validation": "NOT_PERFORMED",
        "predictive_validation": "NOT_PERFORMED",
    }


def build_evaluation(settings, project_root, profile_manifest, *, replicates=20):
    project_root = project_root.resolve()
    profiles, _, verified = load_profiles(settings, project_root, profile_manifest)
    report = evaluate_cohort(profiles, settings, replicates)
    root = base_path(settings, project_root) / EVALUATION_VERSION
    with cohort_lock(root / ".evaluation.lock", project_root):
        data = json_bytes(report)
        sha = digest(data)
        path = f"reports/{sha}.json"
        immutable_write(root / path, data, root)
        manifest = summary(settings, verified, report) | {
            "artifacts": [
                {
                    "kind": "report",
                    "path": path,
                    "sha256": sha,
                    "byte_count": len(data),
                    "record_count": 1,
                }
            ]
        }
        data = json_bytes(manifest)
        sha = digest(data)
        path = root / "manifests" / f"{sha}.json"
        immutable_write(path, data, root)
    return {k: v for k, v in manifest.items() if k not in {"settings", "artifacts"}} | {
        "evaluation_manifest_sha256": sha,
        "evaluation_manifest_path": path.relative_to(project_root).as_posix(),
    }


def verify_evaluation(settings, project_root, manifest_path):
    project_root = project_root.resolve()
    base = base_path(settings, project_root)
    root = base / EVALUATION_VERSION
    data = within(root, manifest_path).read_bytes()
    manifest = strict_json(data)
    if digest(data) != manifest_path.stem or manifest["evaluation_version"] != EVALUATION_VERSION:
        raise IngestionError("Evaluation manifest checksum/version mismatch")
    source = (
        base
        / PROFILE_VERSION
        / "manifests"
        / (manifest["source_profile_manifest_sha256"] + ".json")
    )
    profiles, _, verified = load_profiles(settings, project_root, source)
    report = evaluate_cohort(profiles, settings, manifest["replicates"])
    if {k: v for k, v in manifest.items() if k != "artifacts"} != summary(
        settings, verified, report
    ):
        raise IngestionError("Evaluation settings/report differ from replay")
    artifacts = manifest["artifacts"]
    if len(artifacts) != 1 or artifacts[0]["kind"] != "report":
        raise IngestionError("Unexpected evaluation partition")
    artifact = artifacts[0]
    content = within(root, root / artifact["path"]).read_bytes()
    if (
        content != json_bytes(report)
        or digest(content) != artifact["sha256"]
        or len(content) != artifact["byte_count"]
        or artifact["record_count"] != 1
    ):
        raise IngestionError("Evaluation artifact fails integrity/replay verification")
    return {
        "status": "VERIFIED",
        "evaluation_manifest_sha256": digest(data),
        "replicates": report["replicates"],
        "replayed_from_verified_profiles": True,
    }
