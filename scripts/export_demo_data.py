"""Export a verified V1 snapshot for local static presentation, never publish it."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from football_recruitment import __version__
from football_recruitment.config import load_settings
from football_recruitment.ranking.engine import build_rankings
from football_recruitment.similarity.engine import find_similar_players
from football_recruitment.similarity.pipeline import load_profiles

SCHEMA = "static-demo-1.0.0"
PROFILE_FIELDS = (
    "player_id",
    "player_name",
    "team_id",
    "team_name",
    "competition_id",
    "season_id",
    "primary_position_group",
    "denominator_minutes",
    "dominant_position_share",
    "appearances",
    "peer_eligible",
    "partial_player_season",
    "eligibility_reasons",
    "minutes_convention",
    "profile_version",
)
METRIC_FIELDS = ("value", "unit", "percentile", "peer_count", "coverage", "status", "direction")
CATEGORY_FIELDS = ("score", "status", "metrics", "peer_count", "weights", "component_percentiles")


def encode(value):
    return (
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")


def export_profile(profile):
    result = {key: profile[key] for key in PROFILE_FIELDS}
    result["metrics"] = {
        metric: {key: values[key] for key in METRIC_FIELDS}
        for metric, values in profile["metrics"].items()
    }
    result["categories"] = {
        category: {key: values[key] for key in CATEGORY_FIELDS}
        for category, values in profile["categories"].items()
    }
    return result


def export_snapshot(config_dir, manifest, output_dir):
    config_dir, manifest, output_dir = (
        config_dir.resolve(),
        manifest.resolve(),
        output_dir.resolve(),
    )
    if output_dir.exists():
        raise ValueError("Output already exists; choose a new directory to preserve prior exports")
    # Do not accidentally place provider-derived exports in the tracked demo/source tree.
    repository = Path(__file__).resolve().parents[1]
    if output_dir.is_relative_to(repository) and not output_dir.is_relative_to(
        repository / "outputs"
    ):
        raise ValueError("Repository exports must stay in ignored outputs/, never demo/ or source")
    settings = load_settings(config_dir)
    profiles, _, verified = load_profiles(settings, config_dir.parent, manifest)
    if not verified["full_cohort"]:
        raise ValueError("Static V1 export requires the verified full frozen cohort")
    baseline_path = repository / "docs/BASELINE_PROVENANCE.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    for name, expected in baseline["files"].items():
        if hashlib.sha256((repository / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen source changed: {name}")
    config_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(config_dir.glob("*.toml"))
    }
    for name, expected in config_hashes.items():
        if baseline["files"].get("config/" + name) != expected:
            raise ValueError("Export configuration differs from frozen V1")
    canonical = json.loads((repository / "FINAL_VALIDATION.json").read_text())
    if (
        verified["profile_manifest_sha256"]
        != canonical["reproducibility"]["profile_manifest_sha256"]
    ):
        raise ValueError("Verified snapshot differs from frozen V1 baseline")
    projected = [export_profile(p) for p in profiles]
    data_paths = {
        p["player_id"] + "|" + p["team_id"]: hashlib.sha256(
            (p["player_id"] + "|" + p["team_id"]).encode("utf-8")
        ).hexdigest()
        for p in profiles
    }
    if len(data_paths) != len(profiles) or len(set(data_paths.values())) != len(profiles):
        raise ValueError("Duplicate static profile identity or filename")
    summaries = [
        {
            key: p[key]
            for key in (
                "player_id",
                "player_name",
                "team_id",
                "team_name",
                "primary_position_group",
                "denominator_minutes",
                "peer_eligible",
                "partial_player_season",
            )
        }
        for p in profiles
    ]
    # These are calls to frozen engines. No browser analytical implementation is exported.
    similar = {
        p["player_id"] + "|" + p["team_id"]: find_similar_players(
            profiles, p["player_id"], p["team_id"], settings, top_k=10
        )
        for p in profiles
    }
    rankings = build_rankings(profiles, settings)
    metadata = {
        "schema_version": SCHEMA,
        "package_version": __version__,
        "source_credit": "StatsBomb Open Data",
        "source_repository": settings.dataset.repository,
        "source_revision": settings.dataset.revision,
        "competition": settings.dataset.competition_name,
        "season": settings.dataset.season_name,
        "profile_manifest_sha256": verified["profile_manifest_sha256"],
        "configuration_sha256": config_hashes,
        "full_cohort": True,
        "profile_count": len(profiles),
        "unique_players": len({p["player_id"] for p in profiles}),
        "eligible_profiles": sum(p["peer_eligible"] for p in profiles),
        "minimum_minutes": settings.cohorts.minimum_minutes,
        "minimum_peers": settings.cohorts.minimum_peer_count,
        "roles": ["GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"],
        "requirements": {
            name: r.model_dump(mode="json") for name, r in settings.ranking.requirements.items()
        },
        "maximum_neighbors": 10,
        "ranking_mode": "VERIFIED_PRESETS_ONLY",
        "unsupported_fields": [
            "age",
            "market_value",
            "contracts",
            "injury",
            "transfer_suitability",
        ],
        "publication_status": "LOCAL_PREVIEW_ONLY_RIGHTS_PENDING",
        "disclosure": "Public portfolio demo using a frozen verified V1 dataset snapshot.",
        "hosting_disclosure": (
            "The full analytical pipeline runs in Python. "
            "The static interface uses exported V1 artifacts."
        ),
        "validation": {
            "technical_tests": 220,
            "human_review": "ONE_LIMITED_CASE_03",
            "expert_scout": "PENDING",
            "predictive": "PENDING",
            "general_accuracy_established": False,
            "transfer_suitability_established": False,
        },
        "similarity_statuses": dict(Counter(r["status"] for r in similar.values())),
        "ranking_statuses": {name: r["status"] for name, r in rankings.items()},
        "data_paths": {
            key: {
                "profile": "profiles/" + token + ".json",
                "similarity": "similarity/" + token + ".json",
            }
            for key, token in data_paths.items()
        },
    }
    payloads = {
        "players.json": summaries,
        "ranking_examples.json": rankings,
        "metadata.json": metadata,
    }
    for profile in projected:
        key = profile["player_id"] + "|" + profile["team_id"]
        payloads[metadata["data_paths"][key]["profile"]] = profile
        payloads[metadata["data_paths"][key]["similarity"]] = similar[key]
    files = {name: encode(value) for name, value in payloads.items()}
    export_manifest = {
        "schema_version": SCHEMA,
        "profile_manifest_sha256": verified["profile_manifest_sha256"],
        "publication_status": metadata["publication_status"],
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in files.items()
        },
    }
    output_dir.mkdir(parents=True)
    try:
        for name, data in files.items():
            (output_dir / name).parent.mkdir(parents=True, exist_ok=True)
            (output_dir / name).write_bytes(data)
        # Publish the success manifest last; partial output is never accepted by the UI.
        (output_dir / "manifest.json").write_bytes(encode(export_manifest))
    except OSError as error:
        raise ValueError("Export incomplete; no valid success manifest is available") from error
    return export_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export_snapshot(args.config_dir, args.manifest, args.output_dir)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"Static export failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
