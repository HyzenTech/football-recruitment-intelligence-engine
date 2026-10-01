"""Deterministic repeated reference/candidate thinning, not predictive validation."""

from collections import Counter
from math import isclose
from statistics import fmean

from football_recruitment.ingestion.storage import IngestionError, digest
from football_recruitment.ranking.engine import build_rankings, rank_players
from football_recruitment.similarity.engine import all_queries, find_similar_players

EVALUATION_VERSION = "evaluation-0.8.0"


def retained_players(profiles, replicate):
    return {
        p["player_id"]
        for p in profiles
        if int(digest(f"evaluation-0.8.0:{replicate}:{p['player_id']}".encode())[:8], 16) % 100 < 80
    }


def distribution(values):
    if not values:
        return {"count": 0, "mean": None, "minimum": None, "maximum": None}
    return {
        "count": len(values),
        "mean": fmean(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def audit_results(profiles, similarity, rankings):
    by_id = {(p["player_id"], p["team_id"]): p for p in profiles}
    counts = Counter()

    def require(condition, message):
        if not condition:
            raise IngestionError("Combined evaluation check failed: " + message)

    for q in similarity:
        neighbors = q["neighbors"]
        require(len({n["player_id"] for n in neighbors}) == len(neighbors), "duplicate neighbors")
        require(
            [n["distance"] for n in neighbors] == sorted(n["distance"] for n in neighbors),
            "neighbor order",
        )
        for n in neighbors:
            p = by_id[n["player_id"], n["team_id"]]
            require(
                p["peer_eligible"] and p["primary_position_group"] == q["position_group"],
                "neighbor cohort",
            )
            require(n["player_id"] != q["query"]["player_id"], "query self-exclusion")
            require(
                all(p["metrics"][m]["value"] is not None for m in q["features"]),
                "neighbor completeness",
            )
            require(
                isclose(
                    sum(d["squared_contribution"] for d in n["feature_differences"]),
                    n["distance"] ** 2,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ),
                "distance contributions",
            )
            require(
                isclose(n["similarity_score"], 100 / (1 + n["distance"]), rel_tol=1e-12),
                "similarity index",
            )
            counts["neighbor_rows_checked"] += 1
    for result in rankings.values():
        rows = result["rankings"]
        require(len({r["player_id"] for r in rows}) == len(rows), "duplicate ranked players")
        require(
            [r["recruitment_score"] for r in rows]
            == sorted((r["recruitment_score"] for r in rows), reverse=True),
            "score order",
        )
        for r in rows:
            p = by_id[r["player_id"], r["team_id"]]
            require(
                p["peer_eligible"]
                and p["primary_position_group"] == result["requirement"]["position_group"],
                "ranking cohort",
            )
            require(
                r["denominator_minutes"] >= result["requirement"]["minimum_minutes"],
                "candidate minutes",
            )
            require(r["team_id"] not in result["requirement"]["excluded_team_ids"], "excluded team")
            require(
                set(r["components"]) == set(result["active_metrics"]), "common ranking components"
            )
            require(
                isclose(
                    sum(v["contribution"] for v in r["components"].values()),
                    r["recruitment_score"],
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ),
                "score contributions",
            )
            require(
                isclose(
                    sum(v["normalized_weight"] for v in r["components"].values()),
                    1.0,
                    rel_tol=1e-12,
                ),
                "normalized weights",
            )
            counts["ranked_rows_checked"] += 1
    return {
        "status": "PASS",
        "checks": [
            "position_and_eligibility",
            "player_deduplication",
            "similarity_self_exclusion",
            "complete_vectors",
            "ordering",
            "contribution_arithmetic",
            "candidate_filters",
        ],
        **dict(counts),
    }


def evaluate_cohort(profiles, settings, replicates=20):
    if (
        isinstance(replicates, bool)
        or not isinstance(replicates, int)
        or not 2 <= replicates <= 100
    ):
        raise IngestionError("Evaluation replicates must be an integer from 2 to 100")
    similarity = all_queries(profiles, settings)
    rankings = build_rankings(profiles, settings)
    audit = audit_results(profiles, similarity, rankings)
    sim_records = []
    rank_records = []
    for replicate in range(replicates):
        retained = retained_players(profiles, replicate)
        for base in similarity:
            if base["status"] != "AVAILABLE":
                continue
            q = base["query"]
            variant = find_similar_players(
                profiles, q["player_id"], q["team_id"], settings, reference_player_ids=retained
            )
            old = [n["player_id"] for n in base["neighbors"][:5]]
            new = [n["player_id"] for n in variant["neighbors"][:5]]
            sim_records.append(
                {
                    "replicate": replicate,
                    "player_id": q["player_id"],
                    "team_id": q["team_id"],
                    "position_group": base["position_group"],
                    "status": variant["status"],
                    "peer_count": variant["peer_count"],
                    "baseline_top5": old,
                    "variant_top5": new,
                    "top5_overlap": len(set(old) & set(new)) / len(old)
                    if variant["status"] == "AVAILABLE"
                    else None,
                }
            )
        thinned = [p for p in profiles if p["player_id"] in retained]
        for name, base in rankings.items():
            req = settings.ranking.requirements[name]
            variant = rank_players(thinned, req, settings)
            old = [r["player_id"] for r in base["rankings"][:5]]
            new = [r["player_id"] for r in variant["rankings"][:5]]
            surviving = [p for p in old if p in retained]
            available = base["status"] == variant["status"] == "AVAILABLE"
            rank_records.append(
                {
                    "replicate": replicate,
                    "requirement": name,
                    "baseline_status": base["status"],
                    "status": variant["status"],
                    "peer_count": variant["peer_count"],
                    "baseline_top5": old,
                    "variant_top5": new,
                    "baseline_top5_retained": len(surviving),
                    "top5_overlap": len(set(old) & set(new)) / len(old) if available else None,
                    "surviving_baseline_top5_recovery": len(set(surviving) & set(new))
                    / len(surviving)
                    if available and surviving
                    else None,
                }
            )
    sim_summary = {
        group: {
            "attempts": len(rows),
            "status_counts": dict(sorted(Counter(r["status"] for r in rows).items())),
            "top5_overlap": distribution(
                [r["top5_overlap"] for r in rows if r["top5_overlap"] is not None]
            ),
        }
        for group in sorted({r["position_group"] for r in sim_records})
        for rows in [[r for r in sim_records if r["position_group"] == group]]
    }
    rank_summary = {
        name: {
            "attempts": len(rows),
            "status_counts": dict(sorted(Counter(r["status"] for r in rows).items())),
            "top5_overlap": distribution(
                [r["top5_overlap"] for r in rows if r["top5_overlap"] is not None]
            ),
            "surviving_baseline_top5_recovery": distribution(
                [
                    r["surviving_baseline_top5_recovery"]
                    for r in rows
                    if r["surviving_baseline_top5_recovery"] is not None
                ]
            ),
        }
        for name in sorted(rankings)
        for rows in [[r for r in rank_records if r["requirement"] == name]]
    }
    cases = []
    for group in sorted({q["position_group"] for q in similarity if q["status"] == "AVAILABLE"}):
        q = max(
            (q for q in similarity if q["status"] == "AVAILABLE" and q["position_group"] == group),
            key=lambda q: (q["query"]["denominator_minutes"], q["query"]["player_id"]),
        )
        cases.append(
            {
                "position_group": group,
                "query": q["query"],
                "closest_neighbor": q["neighbors"][0],
                "review": (
                    "Metric-proximity case generated from verified data; "
                    "no expert archetype conclusion"
                ),
            }
        )
    return {
        "evaluation_version": EVALUATION_VERSION,
        "replicates": replicates,
        "retention_rule": (
            "first 8 SHA256 hex digits of evaluation-0.8.0:replicate:player_id modulo 100 < 80"
        ),
        "sampling_unit": "player; all team spells retained or removed together",
        "similarity_experiment": "reference thinning; queries always retained",
        "ranking_experiment": "candidate and reference thinning; benchmark refit",
        "overlap_formula": "intersection(baseline_top5,variant_top5)/baseline_top5_count",
        "availability_policy": (
            "Unavailable attempts counted explicitly and excluded from overlap averages"
        ),
        "interpretation": (
            "Empirical perturbation ranges, not confidence intervals or predictive accuracy"
        ),
        "baseline_similarity_status_counts": dict(
            sorted(Counter(q["status"] for q in similarity).items())
        ),
        "baseline_ranking_status_counts": dict(
            sorted(Counter(r["status"] for r in rankings.values()).items())
        ),
        "combined_checks": audit,
        "similarity_stability": sim_summary,
        "ranking_stability": rank_summary,
        "similarity_records": sim_records,
        "ranking_records": rank_records,
        "football_review": {
            "status": "DATA_ONLY_SANITY_CHECKS_COMPLETE",
            "external_archetype_validation": "NOT_PERFORMED",
            "predictive_validation": "NOT_PERFORMED",
            "limits": [
                "No expert/film review or target outcomes",
                "One historical league and unadjusted team context",
                "Goalkeeper comparisons cover distribution only",
                "Small groups and missing components remain suppressed",
            ],
            "cases": cases,
        },
    }
