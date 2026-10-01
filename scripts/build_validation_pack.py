"""Create a local CB review packet; never fabricate footage or expert observations."""

import argparse
import hashlib
import json
from pathlib import Path

from football_recruitment import __version__
from football_recruitment.config import load_settings
from football_recruitment.features.metrics import FEATURE_VERSION
from football_recruitment.ingestion.storage import digest, strict_json, within
from football_recruitment.ranking.engine import rank_players
from football_recruitment.similarity.engine import find_similar_players
from football_recruitment.similarity.pipeline import load_profiles


def read_rows(base, artifact):
    data = within(base, base / artifact["path"]).read_bytes()
    if digest(data) != artifact["sha256"]:
        raise ValueError("Review input artifact changed after verification")
    return [strict_json(line) for line in data.splitlines() if line.strip()]


def identity(profile):
    return {
        k: profile[k]
        for k in (
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "denominator_minutes",
            "primary_position_group",
            "dominant_position_share",
            "peer_eligible",
        )
    }


def label(player):
    return f"{player['player_name']} - {player['team_name']}"


def fmt(value):
    return "Unavailable" if value is None else f"{value:.2f}"


def table(headers, rows):
    def escape(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    return (
        "\n".join(
            [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
                *("| " + " | ".join(map(escape, row)) + " |" for row in rows),
            ]
        )
        + "\n"
    )


def build(root, config, manifest):
    settings = load_settings(config)
    profiles, report, verified = load_profiles(settings, root, manifest)
    if not verified["full_cohort"]:
        raise ValueError("Pilot requires the full verified cohort")
    index = {(p["player_id"], p["team_id"]): p for p in profiles}
    eligible = sorted(
        (p for p in profiles if p["peer_eligible"] and p["primary_position_group"] == "CB"),
        key=lambda p: (-p["denominator_minutes"], p["player_id"], p["team_id"]),
    )
    pairs, seen, attempted = [], set(), []
    for query in eligible:
        result = find_similar_players(
            profiles, query["player_id"], query["team_id"], settings, top_k=1
        )
        attempted.append({"query": identity(query), "status": result["status"]})
        if result["status"] != "AVAILABLE":
            continue
        neighbor = result["neighbors"][0]
        pair = frozenset((query["player_id"], neighbor["player_id"]))
        if pair in seen:
            continue
        seen.add(pair)
        pairs.append(
            {
                "case_id": f"SIM-{len(pairs) + 1:02d}",
                "query": identity(query),
                "peer": identity(index[neighbor["player_id"], neighbor["team_id"]]),
                "model": result,
            }
        )
        if len(pairs) == 5:
            break
    requirement = settings.ranking.requirements["CB_defensive_activity"]
    ranking = rank_players(profiles, requirement, settings)
    if len(pairs) != 5 or ranking["status"] != "AVAILABLE" or len(ranking["rankings"]) < 5:
        raise ValueError("Not enough available cases for the declared pilot")
    candidates = [
        {
            "case_id": f"RANK-{i:02d}",
            "player": identity(index[p["player_id"], p["team_id"]]),
            "model": p,
        }
        for i, p in enumerate(ranking["rankings"][:5], 1)
    ]
    variants = {}
    for name, update in (
        ("minimum_900", {"minimum_minutes": 900}),
        ("minimum_1350", {"minimum_minutes": 1350}),
        (
            "interceptions_weight_1",
            {"weights": {"interceptions": 1, "tackles": 2, "long_passes": 1}},
        ),
    ):
        request = type(requirement).model_validate(
            requirement.model_dump(mode="json") | update | {"top_k": 100}
        )
        variants[name] = rank_players(profiles, request, settings)
    base = manifest.parent.parent.parent
    feature_base = base / FEATURE_VERSION
    feature_manifest = (
        feature_base / "manifests" / (report["source_feature_manifest_sha256"] + ".json")
    )
    feature_report = strict_json(feature_manifest.read_bytes())
    player_matches = read_rows(
        feature_base, next(a for a in feature_report["artifacts"] if a["kind"] == "player_match")
    )
    d = settings.dataset
    canonical = (
        root
        / d.paths.interim
        / d.provider
        / d.revision
        / f"{d.competition_id}-{d.season_id}"
        / "statsbomb-canonical-0.2.1"
    )
    source = strict_json(
        (canonical / "manifests" / (report["source_manifest_sha256"] + ".json")).read_bytes()
    )
    matches = {
        p["match_id"]: p
        for p in read_rows(
            canonical, next(a for a in source["canonical_artifacts"] if a["kind"] == "matches")
        )
    }
    teams = {p["team_id"]: p["team_name"] for p in profiles}
    players = {
        (p["player_id"], p["team_id"]): p for case in pairs for p in (case["query"], case["peer"])
    }
    players.update(
        {(c["player"]["player_id"], c["player"]["team_id"]): c["player"] for c in candidates}
    )
    footage = []
    for key, player in sorted(players.items()):
        appearances = sorted(
            (p for p in player_matches if (p["player_id"], p["team_id"]) == key),
            key=lambda p: (
                -p["denominator_minutes"],
                matches[p["match_id"]]["match_date"],
                p["match_id"],
            ),
        )[:2]
        for appearance in appearances:
            match = matches[appearance["match_id"]]
            footage.append(
                {
                    "player": player,
                    "match_id": match["match_id"],
                    "match_date": match["match_date"],
                    "fixture": teams[match["home_team_id"]] + " vs " + teams[match["away_team_id"]],
                    "validated_minutes": appearance["denominator_minutes"],
                    "footage_status": "NEEDS_SOURCE",
                    "footage_url": None,
                }
            )
    return {
        "protocol_version": "cb-review-0.1",
        "package_version": __version__,
        "profile_manifest_sha256": verified["profile_manifest_sha256"],
        "source_revision": settings.dataset.revision,
        "source_credit": "StatsBomb Open Data; local noncommercial research",
        "selection": (
            "descending eligible CB minutes; closest available neighbor; skip "
            "duplicate unordered player pairs; first five"
        ),
        "selection_attempts": attempted,
        "pairs": pairs,
        "candidates": candidates,
        "ranking": ranking,
        "variants": variants,
        "footage_locators": footage,
        "expert_review_status": "NOT_PERFORMED",
        "predictive_validation": "NOT_PERFORMED",
    }


def write_pack(pack, destination):
    destination.mkdir(parents=True, exist_ok=False)
    encoded = json.dumps(pack, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (destination / "MODEL_EVIDENCE.json").write_text(encoded, encoding="utf-8")
    cases = [(c["case_id"], [c["query"], c["peer"]]) for c in pack["pairs"]]
    cases += [(c["case_id"], [c["player"]]) for c in pack["candidates"]]
    ordered = sorted(
        cases, key=lambda c: hashlib.sha256(("cb-review-0.1:" + c[0]).encode()).hexdigest()
    )
    aliases = {key: f"CASE-{i:02d}" for i, (key, _) in enumerate(ordered, 1)}
    blind = (
        "# Initial review - keep model evidence closed\n\nReview status: "
        "NOT_PERFORMED. Models selected these cases; this is a "
        "convenience pilot, not a representative or controlled accuracy "
        "study.\n\n"
    )
    results = (
        "# Reviewer results\n\nDo not fill scores before viewing adequate "
        "sourced footage. Leave unknowns blank or mark "
        "NOT_ASSESSABLE.\n\n"
    )
    review_fields = {
        "review_status": "NOT_PERFORMED",
        "reviewer": None,
        "review_date": None,
        "reviewer_experience": None,
        "model_seen_before_review": None,
        "footage_sources_and_timestamps": [],
        "observation_summary": None,
        "context_and_uncertainty": None,
        "blind_pair_similarity_1_to_5": None,
        "blind_requirement_fit_1_to_5": None,
        "confidence_low_medium_high": None,
        "revealed_model_agreement_1_to_5": None,
        "disagreement_reason": None,
        "supported_next_action": None,
    }
    forms = {}
    for key, players in ordered:
        alias = aliases[key]
        blind += (
            f"## {alias} - {'Pair comparison' if len(players) == 2 else 'Candidate review'}\n\n"
        )
        for i, player in enumerate(players, 1):
            blind += (
                f"Player {i}: **{label(player)}**. Historical team-spell IDs: "
                f"`{player['player_id']}`, `{player['team_id']}`.\n\n"
            )
        blind += (
            "Observe anticipation/interceptions, tackling decisions and long "
            "distribution; for pairs also compare carrying, action volume and "
            "involvement. Record context, contradictory examples and "
            "unassessable dimensions before opening model evidence.\n\n"
        )
        results += (
            f"## {alias}\n\n- Status: NOT_PERFORMED\n- Reviewer / experience / "
            f"date:\n- Model evidence seen before review: [ ] Yes [ ] No\n- "
            f"Footage sources, match IDs, timestamps and minutes watched:\n- "
            f"Observations supporting similarity or requirement fit:\n- "
            f"Contradictory examples and team/opponent context:\n- Similarity "
            f"rating (pairs only, 1-5 or NOT_ASSESSABLE):\n- Requirement fit "
            f"(candidates only, 1-5 or NOT_ASSESSABLE):\n- Confidence "
            f"(low/medium/high) and missing evidence:\n- After reveal: "
            f"agreement (1-5), disagreement cause and proposed follow-up:\n\n"
        )
        forms[alias] = dict(review_fields)
    (destination / "BLIND_REVIEW.md").write_text(blind, encoding="utf-8")
    (destination / "REVIEW_RESULTS.md").write_text(results, encoding="utf-8")
    (destination / "REVIEW_RESULTS.json").write_text(
        json.dumps(forms, indent=2) + "\n", encoding="utf-8"
    )
    evidence = (
        "# Model explanations - open after the initial review\n\nSource: "
        "StatsBomb Open Data, WSL 2023/24. Local noncommercial review. "
        "Model evidence is computed; all expert and footage judgments "
        "remain unperformed.\n\n"
    )
    evidence += f"Profile manifest: `{pack['profile_manifest_sha256']}`.\n\n"
    for case in pack["pairs"]:
        result = case["model"]
        neighbor = result["neighbors"][0]
        evidence += (
            f"## {aliases[case['case_id']]} ({case['case_id']}) - "
            f"{label(case['query'])} / {label(case['peer'])}\n\n"
        )
        evidence += (
            f"Validated minutes: {fmt(case['query']['denominator_minutes'])} / "
            f"{fmt(case['peer']['denominator_minutes'])}. Distance "
            f"{fmt(neighbor['distance'])}; index "
            f"{fmt(neighbor['similarity_score'])}; {result['peer_count']} "
            f"complete candidate peers. The index is 100/(1+distance), not a "
            f"probability or ability rating.\n\n"
        )
        evidence += table(
            ["Metric", "Query", "Neighbor", "Unit", "Standardized difference", "Distance share"],
            [
                [
                    d["metric"],
                    fmt(d["query_value"]),
                    fmt(d["peer_value"]),
                    d["unit"],
                    fmt(d["standardized_difference"]),
                    fmt(100 * d["contribution_share"]) + "%",
                ]
                for d in neighbor["feature_differences"]
            ],
        )
        evidence += (
            "\nLargest distance shares identify what to investigate on film; "
            "small shares indicate numeric proximity only. Query-player "
            "spells are excluded, and the scaler is fitted to candidates.\n\n"
        )
    weights = pack["ranking"]["normalized_weights"]
    evidence += (
        "## Recruitment requirement\n\nInterceptions/tackles/long passes "
        "have raw weights 3/2/1; normalized weights: "
        + json.dumps(weights)
        + ". This is defensive event activity plus distribution, not a "
        "complete CB ability model.\n\n"
    )
    for case in pack["candidates"]:
        row = case["model"]
        p = case["player"]
        evidence += f"### {aliases[case['case_id']]} ({case['case_id']}) - {label(p)}\n\n"
        evidence += (
            f"Baseline rank {row['rank']}; requirement score "
            f"{fmt(row['recruitment_score'])}; {fmt(p['denominator_minutes'])} "
            f"validated minutes.\n\n"
        )
        evidence += table(
            ["Metric", "Value", "Unit", "Peer percentile", "Weight", "Contribution", "Coverage"],
            [
                [
                    m,
                    fmt(c["value"]),
                    c["unit"],
                    fmt(c["percentile"]),
                    fmt(c["normalized_weight"]),
                    fmt(c["contribution"]),
                    fmt(100 * c["coverage"]) + "%"
                    if c["coverage"] is not None
                    else "Not applicable",
                ]
                for m, c in row["components"].items()
            ],
        )
        evidence += (
            "\nLower requested dimensions: "
            + ", ".join(
                d["metric"] + " (" + fmt(d["percentile"]) + " percentile)"
                for d in row["weaker_dimensions"]
            )
            + ". Relative ordering alone does not prove a weakness.\n\n"
        )
    evidence += (
        "## Calculated sensitivity - no expert judgment\n\nMinutes "
        "filters retain the same complete reference population. Weight "
        "changes alter the requirement. These checks measure sensitivity, "
        "not football validity.\n\n"
    )
    sensitivity = []
    for c in pack["candidates"]:
        p = c["player"]
        cells = [aliases[c["case_id"]], c["model"]["rank"], fmt(c["model"]["recruitment_score"])]
        for result in pack["variants"].values():
            found = next(
                (
                    r
                    for r in result["rankings"]
                    if (r["player_id"], r["team_id"]) == (p["player_id"], p["team_id"])
                ),
                None,
            )
            cells.append(
                f"rank {found['rank']}, score {fmt(found['recruitment_score'])}"
                if found
                else "Excluded by minutes / unavailable"
            )
        sensitivity.append(cells)
    evidence += table(["Case", "Baseline rank", "Score", *pack["variants"]], sensitivity)
    (destination / "MODEL_EXPLANATIONS.md").write_text(evidence, encoding="utf-8")
    footage = (
        "# Historical fixture locators - footage not yet sourced\n\nTwo "
        "largest validated player-match exposures per selected team "
        "spell; ties use date and match ID. Match metadata is verified "
        "local evidence, not proof that a video is available. Use "
        "authorized footage, check the correct season/player, and record "
        "actual video timestamps. Do not infer video timestamps from "
        "event clocks.\n\n"
    )
    footage += table(
        ["Player / team", "Date", "Fixture", "Match ID", "Validated minutes", "Footage status"],
        [
            [
                label(f["player"]),
                f["match_date"],
                f["fixture"],
                f["match_id"],
                fmt(f["validated_minutes"]),
                f["footage_status"],
            ]
            for f in pack["footage_locators"]
        ],
    )
    footage += (
        "\nThese are whole-match player exposures, not guaranteed CB minutes. "
        "Verify the observed match role on footage.\n"
    )
    (destination / "FOOTAGE_LOCATORS.md").write_text(footage, encoding="utf-8")
    (destination / "START_HERE.md").write_text(
        "# Centre-back validation pilot\n\nStatus: **PACK_READY; EXPERT_REVIEW_NOT_PERFORMED**.\n\n"
        "1. Read REVIEW_PROTOCOL.md and agree on the requirement before seeing model scores.\n"
        "2. Use BLIND_REVIEW.md plus FOOTAGE_LOCATORS.md. Find authorized "
        "footage and complete REVIEW_RESULTS.md or its JSON equivalent.\n"
        "3. Freeze initial observations, then open MODEL_EXPLANATIONS.md. "
        "Record agreement and disagreement without rewriting the initial "
        "notes.\n"
        "4. Summarize assessed/unassessable cases, context and proposed "
        "fixes. Never convert these ten convenience cases into a claimed "
        "accuracy rate.\n\n"
        "Five unique similarity pairs and five requirement candidates; "
        "some players repeat across case types. The JSON evidence retains "
        "exact calculations and provenance. Footage remains NEEDS_SOURCE "
        "and all review fields are blank. This pack stays local and "
        "outside the code archive.\n",
        encoding="utf-8",
    )
    with (destination / "START_HERE.md").open("a", encoding="utf-8") as file:
        file.write(
            "\n[Review protocol](REVIEW_PROTOCOL.md) | [Initial cases](BLIND_REVIEW.md) | "
            "[Footage locators](FOOTAGE_LOCATORS.md) | [Results template](REVIEW_RESULTS.md)\n\n"
            "After the first pass: [model explanations](MODEL_EXPLANATIONS.md).\n"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir", type=Path, default=Path(__file__).resolve().parents[1] / "config"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/cb-validation-pilot"))
    args = parser.parse_args()
    config = args.config_dir.resolve()
    root = config.parent
    try:
        pack = build(root, config, args.manifest.resolve())
        destination = within(root, root / args.output_dir).resolve()
        reports = within(root, root / load_settings(config).dataset.paths.reports).resolve()
        if not destination.is_relative_to(reports) or destination == reports:
            raise ValueError("Review packs must be under ignored local report storage")
        write_pack(pack, destination)
        protocol = root / "docs/FOOTBALL_VALIDATION.md"
        (destination / "REVIEW_PROTOCOL.md").write_text(
            protocol.read_text(encoding="utf-8").replace(
                "../DATA_LICENSE.md",
                "../" * len(destination.relative_to(root).parts) + "DATA_LICENSE.md",
            ),
            encoding="utf-8",
        )
        initial_hashes = {
            p.name: digest(p.read_bytes()) for p in sorted(destination.iterdir()) if p.is_file()
        }
        (destination / "PACK_MANIFEST.json").write_text(
            json.dumps(
                {
                    "status": "PACK_READY",
                    "expert_review": "NOT_PERFORMED",
                    "profile_manifest_sha256": pack["profile_manifest_sha256"],
                    "initial_file_sha256": initial_hashes,
                    "note": "Hashes describe initial blank forms; reviewer edits are expected",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "PACK_READY",
                    "path": str(destination),
                    "pair_cases": 5,
                    "candidate_cases": 5,
                    "expert_review": "NOT_PERFORMED",
                }
            )
        )
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Pack failed: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
