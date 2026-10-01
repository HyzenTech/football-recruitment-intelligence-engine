"""Declared sensitivity experiments; no claim of predictive scouting accuracy."""

from copy import deepcopy
from statistics import fmean

from football_recruitment.ingestion.storage import digest
from football_recruitment.similarity.engine import find_similar_players

ABLATIONS = {
    "without_passing": {"passes_attempted", "long_passes"},
    "without_carrying": {"carries", "carry_displacement"},
    "without_shooting": {"shots", "nonpenalty_xg"},
    "without_defending": {"pressures", "interceptions", "tackles", "recoveries"},
    "without_attacking_zones": {"final_third_actions", "box_actions"},
}


def evaluate_similarity(profiles, settings, baseline):
    variants = [("robust_scaling", None, {"scaling": "robust"})]
    for threshold in (300.0, 600.0):
        changed = deepcopy(profiles)
        for p in changed:
            reasons = [r for r in p["eligibility_reasons"] if r != "BELOW_MINIMUM_MINUTES"]
            if p["denominator_minutes"] < threshold:
                reasons.append("BELOW_MINIMUM_MINUTES")
            p.update(eligibility_reasons=reasons, peer_eligible=not reasons)
        variants.append((f"minimum_minutes_{int(threshold)}", changed, {}))
    for name in ABLATIONS:
        variants.append((name, None, {}))
    retained = {
        p["player_id"] for p in profiles if int(digest(p["player_id"].encode())[:8], 16) % 5 != 0
    }
    variants.append(("reference_subsample_80_percent", None, {"reference_player_ids": retained}))
    results = []
    for name, changed, options in variants:
        records = []
        not_applicable = 0
        for base in baseline:
            if base["status"] != "AVAILABLE":
                continue
            group = base["position_group"]
            args = dict(options)
            if name in ABLATIONS:
                selected = [
                    m for m in settings.similarity.features[group] if m not in ABLATIONS[name]
                ]
                if not selected or len(selected) == len(settings.similarity.features[group]):
                    not_applicable += 1
                    continue
                args["features"] = selected
            query = base["query"]
            result = find_similar_players(
                changed or profiles, query["player_id"], query["team_id"], settings, **args
            )
            old = [n["player_id"] for n in base["neighbors"][:5]]
            new = [n["player_id"] for n in result["neighbors"][:5]]
            records.append(
                {
                    "player_id": query["player_id"],
                    "team_id": query["team_id"],
                    "status": result["status"],
                    "baseline_top5": old,
                    "variant_top5": new,
                    "top5_overlap": len(set(old) & set(new)) / len(old)
                    if result["status"] == "AVAILABLE"
                    else None,
                }
            )
        overlaps = [r["top5_overlap"] for r in records if r["top5_overlap"] is not None]
        results.append(
            {
                "scenario": name,
                "baseline_queries_evaluated": len(records),
                "not_applicable_queries": not_applicable,
                "queries_remaining_available": len(overlaps),
                "mean_top5_overlap": fmean(overlaps) if overlaps else None,
                "records": records,
            }
        )
    return {
        "baseline_minimum_minutes": settings.cohorts.minimum_minutes,
        "baseline_scaling": settings.similarity.scaling,
        "overlap_formula": "intersection(baseline_top5,variant_top5)/len(baseline_top5)",
        "subsample_rule": "keep player if first 8 SHA256 hex digits modulo 5 is nonzero",
        "baseline_available_queries": sum(r["status"] == "AVAILABLE" for r in baseline),
        "scenarios": results,
        "interpretation": "Sensitivity diagnostics only; not football or predictive validation",
    }
