"""Requirement-specific weighted percentiles on a common complete population."""

from math import fsum, isfinite

from football_recruitment.config import RankingRequirement
from football_recruitment.ingestion.storage import IngestionError
from football_recruitment.normalization.engine import LOWER, percentile

RANKING_VERSION = "ranking-0.7.0"


def rank_players(profiles, requirement, settings):
    requirement = RankingRequirement.model_validate(
        requirement.model_dump() if isinstance(requirement, RankingRequirement) else requirement
    )
    if requirement.minimum_minutes < settings.cohorts.minimum_minutes:
        raise IngestionError("Requirement cannot lower the verified profile minimum minutes")
    active = sorted(m for m, w in requirement.weights.items() if w > 0)
    maximum = max(requirement.weights.values())
    scaled = {m: requirement.weights[m] / maximum for m in active}
    total = fsum(scaled.values())
    weights = {m: scaled[m] / total for m in active}
    seen, spells, exclusions = set(), {}, []
    for p in sorted(profiles, key=lambda p: (p["player_id"], p["team_id"])):
        identity = p["player_id"], p["team_id"]
        if identity in seen:
            raise IngestionError("Duplicate ranking profile identity")
        seen.add(identity)
        reasons = []
        if p["primary_position_group"] != requirement.position_group:
            reasons.append("NOT_REQUESTED_POSITION")
        elif not p["peer_eligible"]:
            reasons.extend(p["eligibility_reasons"])
        if reasons:
            exclusions.append(
                {"player_id": identity[0], "team_id": identity[1], "reasons": reasons}
            )
            continue
        old = spells.get(p["player_id"])
        if old is None or (-p["denominator_minutes"], p["team_id"]) < (
            -old["denominator_minutes"],
            old["team_id"],
        ):
            spells[p["player_id"]] = p
    selected = {(p["player_id"], p["team_id"]) for p in spells.values()}
    for p in profiles:
        if (
            p["peer_eligible"]
            and p["primary_position_group"] == requirement.position_group
            and (p["player_id"], p["team_id"]) not in selected
        ):
            exclusions.append(
                {
                    "player_id": p["player_id"],
                    "team_id": p["team_id"],
                    "reasons": ["SHORTER_OR_TIED_TEAM_SPELL"],
                }
            )
    peers = []
    for p in sorted(spells.values(), key=lambda p: (p["player_id"], p["team_id"])):
        missing = [m for m in active if p["metrics"][m]["value"] is None]
        if missing:
            exclusions.append(
                {
                    "player_id": p["player_id"],
                    "team_id": p["team_id"],
                    "reasons": ["MISSING_REQUIRED_METRICS"],
                    "missing_metrics": missing,
                }
            )
            continue
        if any(not isfinite(p["metrics"][m]["value"]) for m in active):
            raise IngestionError("Ranking requires finite metric values")
        peers.append(p)
    result = {
        "ranking_version": RANKING_VERSION,
        "requirement": requirement.model_dump(mode="json"),
        "normalized_weights": weights,
        "active_metrics": active,
        "ignored_zero_weight_metrics": sorted(m for m, w in requirement.weights.items() if w == 0),
        "peer_count": len(peers),
        "minimum_peer_count": settings.cohorts.minimum_peer_count,
        "reference_ids": [[p["player_id"], p["team_id"]] for p in peers],
        "reference_policy": "common_complete_role_population; longest_eligible_spell_per_player",
        "percentile_formula": "100*(count_less+0.5*count_equal)/n; lower uses 100-result",
        "score_formula": "sum(normalized_weight*direction_aware_common_population_percentile)",
        "candidate_filter_policy": "minimum_minutes_and_excluded_teams_after_reference_selection",
        "exclusions": sorted(exclusions, key=lambda e: (e["player_id"], e["team_id"])),
        "rankings": [],
        "candidate_count": 0,
        "warnings": [],
    }
    if len(peers) < settings.cohorts.minimum_peer_count:
        return result | {"status": "INSUFFICIENT_PEERS"}
    constant = [m for m in active if len({p["metrics"][m]["value"] for p in peers}) == 1]
    if constant:
        return result | {"status": "CONSTANT_COMPONENT", "constant_metrics": constant}
    rows = []
    for p in peers:
        reasons = []
        if p["denominator_minutes"] < requirement.minimum_minutes:
            reasons.append("BELOW_REQUIREMENT_MINUTES")
        if p["team_id"] in requirement.excluded_team_ids:
            reasons.append("EXCLUDED_TEAM")
        if reasons:
            result["exclusions"].append(
                {"player_id": p["player_id"], "team_id": p["team_id"], "reasons": reasons}
            )
            continue
        components = {}
        for m in active:
            value = p["metrics"][m]["value"]
            pct = percentile(value, [r["metrics"][m]["value"] for r in peers], lower=m in LOWER)
            components[m] = {
                "value": value,
                "unit": p["metrics"][m]["unit"],
                "direction": "lower" if m in LOWER else "higher",
                "percentile": pct,
                "normalized_weight": weights[m],
                "contribution": weights[m] * pct,
                "coverage": p["metrics"][m]["coverage"],
            }
        row = {
            k: p[k]
            for k in (
                "player_id",
                "player_name",
                "team_id",
                "team_name",
                "denominator_minutes",
                "primary_position_group",
            )
        }
        row.update(
            recruitment_score=fsum(v["contribution"] for v in components.values()),
            components=components,
            ranking_reasons=[
                {"metric": m, **v}
                for m, v in sorted(
                    components.items(), key=lambda kv: (-kv[1]["contribution"], kv[0])
                )[:3]
            ],
            weaker_dimensions=[
                {"metric": m, **v}
                for m, v in sorted(components.items(), key=lambda kv: (kv[1]["percentile"], kv[0]))[
                    :3
                ]
            ],
        )
        rows.append(row)
    ordered = sorted(rows, key=lambda r: (-r["recruitment_score"], r["player_id"], r["team_id"]))
    for rank, row in enumerate(ordered, 1):
        row["rank"] = rank
    result.update(
        candidate_count=len(ordered),
        rankings=ordered[: requirement.top_k],
        exclusions=sorted(result["exclusions"], key=lambda e: (e["player_id"], e["team_id"])),
    )
    if len(ordered) < requirement.top_k:
        result["warnings"].append("FEWER_CANDIDATES_THAN_REQUESTED")
    return result | {"status": "AVAILABLE" if ordered else "NO_CANDIDATES"}


def build_rankings(profiles, settings):
    return {
        name: rank_players(profiles, requirement, settings)
        for name, requirement in sorted(settings.ranking.requirements.items())
    }


def evaluate_rankings(profiles, settings, rankings):
    scenarios = []
    for name, base in sorted(rankings.items()):
        requirement = settings.ranking.requirements[name]
        changes = [
            ("minimum_minutes_600", {"minimum_minutes": max(600.0, requirement.minimum_minutes)})
        ]
        for metric in base["active_metrics"]:
            changed = dict(requirement.weights)
            changed[metric] *= 1.5
            if not isfinite(changed[metric]):
                continue
            changes.append((f"weight_x1.5:{metric}", {"weights": changed}))
        old = [r["player_id"] for r in base["rankings"][:5]]
        for scenario, update in changes:
            changed = rank_players(
                profiles,
                RankingRequirement.model_validate(requirement.model_dump() | update),
                settings,
            )
            new = [r["player_id"] for r in changed["rankings"][:5]]
            common = set(old) & set(new)
            scenarios.append(
                {
                    "requirement": name,
                    "scenario": scenario,
                    "baseline_status": base["status"],
                    "variant_status": changed["status"],
                    "baseline_top5": old,
                    "variant_top5": new,
                    "top5_overlap": len(common) / len(old)
                    if old and changed["status"] == "AVAILABLE"
                    else None,
                    "mean_absolute_top5_rank_shift": fsum(
                        abs(old.index(p) - new.index(p)) for p in common
                    )
                    / len(common)
                    if common
                    else None,
                }
            )
    return {
        "weight_multiplier": 1.5,
        "top5_overlap_formula": "intersection_size/baseline_top5_count",
        "interpretation": "Requirement sensitivity diagnostics, not scouting accuracy",
        "scenarios": scenarios,
    }
