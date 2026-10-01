"""Validate local settings or ingest one pinned StatsBomb cohort."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from football_recruitment import __version__
from football_recruitment.config import RankingRequirement, load_settings
from football_recruitment.evaluation.pipeline import build_evaluation, verify_evaluation
from football_recruitment.features.pipeline import build_features
from football_recruitment.features.verification import verify_features
from football_recruitment.ingestion.pipeline import ingest_cohort
from football_recruitment.ingestion.storage import strict_json
from football_recruitment.ingestion.verification import verify_manifest
from football_recruitment.normalization.pipeline import build_profile_artifacts, verify_profiles
from football_recruitment.ranking.engine import rank_players
from football_recruitment.ranking.pipeline import build_ranking_artifacts, verify_rankings
from football_recruitment.similarity.engine import find_similar_players
from football_recruitment.similarity.pipeline import (
    build_similarity,
    load_profiles,
    verify_similarity,
)
from football_recruitment.validation.pipeline import validate_cohort
from football_recruitment.validation.verification import verify_minutes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Football recruitment research foundation")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Validate local configuration; perform no data reads")
    check.add_argument("--config-dir", type=Path, default=Path("config"))
    commands.add_parser("status", help="Show implemented and deferred phases")
    ingest = commands.add_parser("ingest", help="Fetch/cache and canonicalize the pinned cohort")
    ingest.add_argument("--config-dir", type=Path, default=Path("config"))
    ingest.add_argument("--offline", action="store_true", help="Require a verified local raw cache")
    ingest.add_argument("--limit", type=int, help="Diagnostic subset; never claims full ingestion")
    ingest.add_argument("--workers", type=int, default=2, help="Bounded worker count, 1..4")
    verify = commands.add_parser("verify", help="Verify manifest/artifact integrity offline")
    verify.add_argument("--config-dir", type=Path, default=Path("config"))
    verify.add_argument("--manifest", type=Path, required=True)
    validate = commands.add_parser("validate", help="Reconcile appearances and minutes offline")
    validate.add_argument("--config-dir", type=Path, default=Path("config"))
    validate.add_argument("--manifest", type=Path, required=True)
    verify_processed = commands.add_parser(
        "verify-minutes", help="Verify processed interval artifacts"
    )
    verify_processed.add_argument("--config-dir", type=Path, default=Path("config"))
    verify_processed.add_argument("--manifest", type=Path, required=True)
    features = commands.add_parser(
        "build-features", help="Build canonical player-match and season features offline"
    )
    features.add_argument("--config-dir", type=Path, default=Path("config"))
    features.add_argument("--manifest", type=Path, required=True)
    feature_verify = commands.add_parser(
        "verify-features", help="Verify feature aggregates and exposure offline"
    )
    feature_verify.add_argument("--config-dir", type=Path, default=Path("config"))
    feature_verify.add_argument("--manifest", type=Path, required=True)
    for command, help_text in (
        ("build-profiles", "Build positional profiles offline"),
        ("verify-profiles", "Replay profiles from verified upstream artifacts"),
    ):
        sub = commands.add_parser(command, help=help_text)
        sub.add_argument("--config-dir", type=Path, default=Path("config"))
        sub.add_argument("--manifest", type=Path, required=True)
    for command in ("build-similarity", "verify-similarity", "find-similar"):
        sub = commands.add_parser(command, help="Offline positional player similarity")
        sub.add_argument("--config-dir", type=Path, default=Path("config"))
        sub.add_argument("--manifest", type=Path, required=True)
        if command == "find-similar":
            sub.add_argument("--player-id", required=True)
            sub.add_argument("--team-id", required=True)
            sub.add_argument(
                "--position-group", choices=["GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"]
            )
            sub.add_argument("--top-k", type=int)
    for command in ("build-rankings", "verify-rankings", "rank-players"):
        sub = commands.add_parser(command, help="Transparent recruitment ranking offline")
        sub.add_argument("--config-dir", type=Path, default=Path("config"))
        sub.add_argument("--manifest", type=Path, required=True)
        if command == "rank-players":
            select = sub.add_mutually_exclusive_group(required=True)
            select.add_argument("--preset")
            select.add_argument("--requirement", type=Path)
    for command in ("build-evaluation", "verify-evaluation"):
        sub = commands.add_parser(
            command, help="Combined acceptance and repeated stability diagnostics"
        )
        sub.add_argument("--config-dir", type=Path, default=Path("config"))
        sub.add_argument("--manifest", type=Path, required=True)
        if command == "build-evaluation":
            sub.add_argument("--replicates", type=int, default=20)
    local = commands.add_parser("serve", help="Open a loopback-only analytics interface")
    local.add_argument("--config-dir", type=Path, default=Path("config"))
    local.add_argument("--manifest", type=Path, required=True)
    local.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if args.command == "status":
        print(
            json.dumps(
                {
                    "version": __version__,
                    "completed_phase": 10,
                    "implemented": [
                        "canonical_contracts",
                        "provider_interfaces",
                        "local_config_validation",
                        "pinned_ingestion_and_canonical_mapping",
                        "appearance_and_minutes_validation",
                        "player_match_and_season_features",
                        "positional_percentiles_and_profiles",
                        "explained_positional_similarity",
                        "transparent_requirement_rankings",
                        "combined_evaluation_and_repeated_stability",
                        "local_interface_and_api",
                        "portfolio_documentation_and_reproduction",
                    ],
                    "provider_adapters_implemented": ["statsbomb_open_data"],
                    "deferred": [
                        "external_expert_and_predictive_validation",
                        "additional_provider_adapters",
                        "deployment_and_monitoring",
                        "llm_scouting_interface",
                    ],
                },
                indent=2,
            )
        )
        return 0
    try:
        if args.command == "serve":
            from football_recruitment.api.app import serve

            serve(args.config_dir.resolve(), args.manifest.resolve(), args.port)
            return 0
        settings = load_settings(args.config_dir)
        if args.command in {"build-evaluation", "verify-evaluation"}:
            root, manifest = args.config_dir.resolve().parent, args.manifest.resolve()
            result = (
                build_evaluation(settings, root, manifest, replicates=args.replicates)
                if args.command == "build-evaluation"
                else verify_evaluation(settings, root, manifest)
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command in {"build-rankings", "verify-rankings", "rank-players"}:
            root, manifest = args.config_dir.resolve().parent, args.manifest.resolve()
            if args.command == "rank-players":
                if args.preset:
                    if args.preset not in settings.ranking.requirements:
                        raise ValueError("Unknown ranking preset")
                    requirement = settings.ranking.requirements[args.preset]
                else:
                    requirement = RankingRequirement.model_validate(
                        strict_json(args.requirement.read_bytes())
                    )
                profiles, _, _ = load_profiles(settings, root, manifest)
                result = rank_players(profiles, requirement, settings)
            else:
                operation = (
                    build_ranking_artifacts if args.command == "build-rankings" else verify_rankings
                )
                result = operation(settings, root, manifest)
            print(json.dumps(result, indent=2))
            return 0
        if args.command in {"build-similarity", "verify-similarity", "find-similar"}:
            root, manifest = args.config_dir.resolve().parent, args.manifest.resolve()
            if args.command == "find-similar":
                profiles, _, _ = load_profiles(settings, root, manifest)
                result = find_similar_players(
                    profiles,
                    args.player_id,
                    args.team_id,
                    settings,
                    position_group=args.position_group,
                    top_k=args.top_k,
                )
            else:
                operation = (
                    build_similarity if args.command == "build-similarity" else verify_similarity
                )
                result = operation(settings, root, manifest)
            print(json.dumps(result, indent=2))
            return 0
        if args.command in {"build-profiles", "verify-profiles"}:
            operation = (
                build_profile_artifacts if args.command == "build-profiles" else verify_profiles
            )
            print(
                json.dumps(
                    operation(settings, args.config_dir.resolve().parent, args.manifest.resolve()),
                    indent=2,
                )
            )
            return 0
        if args.command == "verify-features":
            print(
                json.dumps(
                    verify_features(
                        settings, args.config_dir.resolve().parent, args.manifest.resolve()
                    ),
                    indent=2,
                )
            )
            return 0
        if args.command == "build-features":

            def feature_progress(completed, total):
                if completed % 10 == 0 or completed == total:
                    print(f"Built features for {completed}/{total} matches", file=sys.stderr)

            result = build_features(
                settings,
                args.config_dir.resolve().parent,
                args.manifest.resolve(),
                progress=feature_progress,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "verify-minutes":
            print(
                json.dumps(
                    verify_minutes(
                        settings, args.config_dir.resolve().parent, args.manifest.resolve()
                    ),
                    indent=2,
                )
            )
            return 0
        if args.command == "validate":

            def validation_progress(completed, total):
                if completed % 10 == 0 or completed == total:
                    print(f"Validated {completed}/{total} matches", file=sys.stderr)

            result = validate_cohort(
                settings,
                args.config_dir.resolve().parent,
                args.manifest.resolve(),
                progress=validation_progress,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "verify":
            result = verify_manifest(
                settings, args.config_dir.resolve().parent, args.manifest.resolve()
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "ingest":

            def progress(completed, total, failures):
                if completed % 10 == 0 or completed == total:
                    print(
                        f"Mapped {completed}/{total} matches; failures={failures}", file=sys.stderr
                    )

            result = ingest_cohort(
                settings,
                args.config_dir.resolve().parent,
                offline=args.offline,
                limit=args.limit,
                workers=args.workers,
                progress=progress,
            )
            print(json.dumps(result, indent=2))
            return 2 if result["status"] == "FAILED" else 0
    except (OSError, ValueError, ValidationError) as error:
        print(f"Command failed: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "configuration": "valid",
                "data_validation": "not_run",
                "provider_adapter": "statsbomb_open_data",
                "network_access": False,
                "competition": settings.dataset.competition_name,
                "season": settings.dataset.season_name,
                "revision": settings.dataset.revision,
                "expected_matches": settings.dataset.expected_match_count,
                "required_future_capabilities": [
                    c.value for c in settings.dataset.required_capabilities
                ],
                "age_filter_enabled": settings.ranking.age_filter_enabled,
                "metric_status": settings.metrics.status,
                "cohort_status": settings.cohorts.status,
            },
            indent=2,
        )
    )
    return 0
