"""Build the configured full cohort with existing CLI stages and optional local UI."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from football_recruitment import __version__
from football_recruitment.config import load_settings


def command(root, config, name, *arguments):
    print(f"Running {name}...", file=sys.stderr, flush=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "football_recruitment",
            name,
            "--config-dir",
            str(config),
            *map(str, arguments),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode:
        if result.stdout:
            print(result.stdout, file=sys.stderr, end="")
        raise ValueError(f"{name} failed (exit {result.returncode}); later stages were not run")
    return json.loads(result.stdout)


def manifest(root, result, key):
    path = (root / result[key]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Invalid {key}: must be an existing artifact inside the project")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir", type=Path, default=Path(__file__).resolve().parents[1] / "config"
    )
    parser.add_argument("--offline", action="store_true", help="Use verified provider cache only")
    parser.add_argument(
        "--serve", action="store_true", help="Launch the local UI after verification"
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be from 1024 to 65535")
    config = args.config_dir.resolve()
    root = config.parent
    try:
        settings = load_settings(config)
        ingestion = command(root, config, "ingest", *(["--offline"] if args.offline else []))
        if ingestion["status"] != "COMPLETE":
            raise ValueError("Reproduction requires complete ingestion")
        canonical = manifest(root, ingestion, "manifest_path")
        command(root, config, "verify", "--manifest", canonical)
        minutes = command(root, config, "validate", "--manifest", canonical)
        minutes_path = manifest(root, minutes, "validation_manifest_path")
        command(root, config, "verify-minutes", "--manifest", minutes_path)
        features = command(root, config, "build-features", "--manifest", minutes_path)
        feature_path = manifest(root, features, "feature_manifest_path")
        command(root, config, "verify-features", "--manifest", feature_path)
        profiles = command(root, config, "build-profiles", "--manifest", feature_path)
        profile_path = manifest(root, profiles, "profile_manifest_path")
        command(root, config, "verify-profiles", "--manifest", profile_path)
        outputs = {
            "ingestion": ingestion,
            "minutes": minutes,
            "features": features,
            "profiles": profiles,
        }
        for name, build, verify in (
            ("similarity", "build-similarity", "verify-similarity"),
            ("ranking", "build-rankings", "verify-rankings"),
            ("evaluation", "build-evaluation", "verify-evaluation"),
        ):
            result = command(root, config, build, "--manifest", profile_path)
            path = manifest(root, result, name + "_manifest_path")
            command(root, config, verify, "--manifest", path)
            outputs[name] = result
        receipt = {
            "package_version": __version__,
            "status": "VERIFIED_END_TO_END",
            "source_revision": settings.dataset.revision,
            "profile_manifest_path": profile_path.relative_to(root).as_posix(),
            "stages": {
                name: {k: v for k, v in result.items() if "manifest" in k}
                for name, result in outputs.items()
            },
            "external_expert_validation": "NOT_PERFORMED",
            "predictive_validation": "NOT_PERFORMED",
        }
        destination = root / settings.dataset.paths.reports / "v1-reproduction.json"
        if not destination.resolve().is_relative_to(root):
            raise ValueError("Reproduction receipt cannot escape the project")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2))
        if args.serve:
            return subprocess.call(
                [
                    sys.executable,
                    "-m",
                    "football_recruitment",
                    "serve",
                    "--config-dir",
                    str(config),
                    "--manifest",
                    str(profile_path),
                    "--port",
                    str(args.port),
                ],
                cwd=root,
            )
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Reproduction failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
