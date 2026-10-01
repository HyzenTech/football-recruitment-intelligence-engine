"""Pure positional assignment, peer eligibility and interpretable profile calculations."""

from collections import defaultdict
from math import isfinite

from football_recruitment.domain.models import PositionGroup
from football_recruitment.features.metrics import MEANS, METRICS, PERCENTAGES
from football_recruitment.ingestion.storage import IngestionError

PROFILE_VERSION = "profiles-0.5.0"
NEUTRAL = set(MEANS)
LOWER = {"miscontrols", "dispossessions"}
CATEGORIES = {
    "passing": ["passes_attempted", "passes_completed", "pass_completion_pct"],
    "progression": ["progressive_passes", "progressive_carries"],
    "carrying": ["carries", "carry_displacement", "carries_into_final_third"],
    "creation": ["shot_assists", "shot_linked_xg_assisted"],
    "shooting": ["nonpenalty_xg", "shots_on_target", "shots"],
    "defensive_activity": ["pressures", "interceptions", "tackles", "recoveries"],
    "retention": ["pass_completion_pct", "miscontrols", "dispossessions"],
    "attacking_involvement": ["final_third_actions", "box_actions"],
}
GK_CATEGORIES = {"distribution_activity": ["passes_attempted", "long_passes"], "shot_stopping": []}


def percentile(value, population, *, lower=False):
    """Mid-distribution percentile; ties share a rank. Constant populations are unavailable."""
    if not population or not all(isfinite(x) for x in [value, *population]):
        raise IngestionError("Percentiles require finite values and nonempty populations")
    if len(set(population)) == 1:
        return None
    less = sum(x < value for x in population)
    equal = sum(x == value for x in population)
    result = 100.0 * (less + 0.5 * equal) / len(population)
    return 100.0 - result if lower else result


def metric_value(row, metric):
    return row["values"][metric]["value" if metric in MEANS + PERCENTAGES else "per90"]


def build_profiles(rows, role_seconds, settings):
    """Keep one reference observation per player/role, selecting the longest eligible team spell."""
    cohorts = settings.cohorts
    profiles = []
    seen = set()
    for row in rows:
        key = row["player_id"], row["team_id"]
        if key in seen:
            raise IngestionError("Duplicate feature player-team identity")
        seen.add(key)
        seconds = role_seconds.get(key, {})
        if abs(sum(seconds.values()) - row["playing_seconds"]) > 1e-6:
            raise IngestionError("Positional duration differs from feature exposure")
        if any(v < 0 or not isfinite(v) for v in seconds.values()):
            raise IngestionError("Invalid positional duration")
        if not set(seconds) <= {g.value for g in PositionGroup} or row["playing_seconds"] <= 0:
            raise IngestionError("Unknown position group or nonpositive exposure")
        primary = max(seconds, key=lambda k: (seconds[k], k)) if seconds else None
        share = seconds[primary] / row["playing_seconds"] if primary else 0.0
        role = primary if share >= cohorts.dominant_role_minimum_share else None
        reasons = []
        if row["minutes_convention"] != cohorts.minutes_convention:
            raise IngestionError("Feature and cohort minute conventions differ")
        if row["denominator_minutes"] < cohorts.minimum_minutes:
            reasons.append("BELOW_MINIMUM_MINUTES")
        if row["partial_player_season"]:
            reasons.append("PARTIAL_PLAYER_SEASON")
        if role is None:
            reasons.append("MIXED_POSITION_USAGE")
        profiles.append(
            {
                "profile_version": PROFILE_VERSION,
                **{
                    k: row[k]
                    for k in (
                        "player_id",
                        "player_name",
                        "team_id",
                        "team_name",
                        "competition_id",
                        "season_id",
                        "playing_seconds",
                        "denominator_minutes",
                        "minutes_convention",
                        "appearances",
                        "excluded_appearances",
                        "partial_player_season",
                    )
                },
                "role_seconds": dict(sorted(seconds.items())),
                "role_shares": {k: v / row["playing_seconds"] for k, v in sorted(seconds.items())},
                "primary_position_group": role,
                "largest_position_group": primary,
                "dominant_position_share": share,
                "peer_eligible": not reasons,
                "eligibility_reasons": reasons,
                "metrics": {},
                "categories": {},
            }
        )
    references = defaultdict(dict)
    sources = {(r["player_id"], r["team_id"]): r for r in rows}
    for p in profiles:
        if p["peer_eligible"]:
            group = p["primary_position_group"]
            previous = references[group].get(p["player_id"])
            if previous is None or (-p["denominator_minutes"], p["team_id"]) < (
                -previous["denominator_minutes"],
                previous["team_id"],
            ):
                references[group][p["player_id"]] = p
    reference_sets = {}

    def population(group, metrics):
        key = group + ":" + "+".join(metrics)
        if key not in reference_sets:
            candidates = sorted(
                references[group].values(), key=lambda p: (p["player_id"], p["team_id"])
            )
            complete = [
                p
                for p in candidates
                if all(
                    metric_value(sources[p["player_id"], p["team_id"]], m) is not None
                    for m in metrics
                )
            ]
            reference_sets[key] = {
                "position_group": group,
                "metrics": metrics,
                "reference_ids": [[p["player_id"], p["team_id"]] for p in complete],
                "peer_count": len(complete),
            }
        ref = reference_sets[key]
        return key, [sources[tuple(ids)] for ids in ref["reference_ids"]]

    for p in profiles:
        source = sources[p["player_id"], p["team_id"]]
        group = p["primary_position_group"]
        for metric in METRICS:
            raw = source["values"][metric]
            value = metric_value(source, metric)
            result = {
                "value": value,
                "unit": "raw" if metric in MEANS + PERCENTAGES else "per90",
                "raw_total_or_mean": raw["value"],
                "coverage": raw["coverage"],
                "missing": raw["missing"],
                "direction": "descriptive"
                if metric in NEUTRAL
                else ("lower" if metric in LOWER else "higher"),
                "percentile": None,
                "peer_count": 0,
                "reference_key": None,
            }
            if metric in NEUTRAL or (
                group == "GK"
                and metric
                not in {
                    "passes_attempted",
                    "long_passes",
                    "passes_completed",
                    "pass_completion_pct",
                }
            ):
                result["status"] = "DESCRIPTIVE_ONLY"
            elif not p["peer_eligible"]:
                result["status"] = "INELIGIBLE_PROFILE"
            elif value is None:
                result["status"] = "MISSING_METRIC"
            else:
                ref_key, reference = population(group, [metric])
                result.update(peer_count=len(reference), reference_key=ref_key)
                if len(reference) < cohorts.minimum_peer_count:
                    result["status"] = "INSUFFICIENT_PEERS"
                else:
                    pct = percentile(
                        value, [metric_value(r, metric) for r in reference], lower=metric in LOWER
                    )
                    result.update(
                        percentile=pct, status="AVAILABLE" if pct is not None else "CONSTANT_METRIC"
                    )
            p["metrics"][metric] = result
        categories = GK_CATEGORIES if group == "GK" else CATEGORIES
        for category, metrics in categories.items():
            result = {
                "metrics": metrics,
                "weights": {m: 1 / len(metrics) for m in metrics},
                "score": None,
                "peer_count": 0,
                "reference_key": None,
                "component_percentiles": {},
            }
            if not metrics:
                result["status"] = "UNSUPPORTED_DATA"
            elif not p["peer_eligible"]:
                result["status"] = "INELIGIBLE_PROFILE"
            elif any(metric_value(source, m) is None for m in metrics):
                result["status"] = "MISSING_COMPONENT"
            else:
                ref_key, reference = population(group, metrics)
                result.update(peer_count=len(reference), reference_key=ref_key)
                if len(reference) < cohorts.minimum_peer_count:
                    result["status"] = "INSUFFICIENT_PEERS"
                else:
                    components = {
                        m: percentile(
                            metric_value(source, m),
                            [metric_value(r, m) for r in reference],
                            lower=m in LOWER,
                        )
                        for m in metrics
                    }
                    result["component_percentiles"] = components
                    if any(v is None for v in components.values()):
                        result["status"] = "CONSTANT_COMPONENT"
                    else:
                        result.update(
                            score=sum(components.values()) / len(metrics), status="AVAILABLE"
                        )
            p["categories"][category] = result
        available = [
            (m, v["percentile"]) for m, v in p["metrics"].items() if v["status"] == "AVAILABLE"
        ]
        p["relative_highlights"] = [
            {"metric": m, "percentile": v}
            for m, v in sorted(available, key=lambda x: (-x[1], x[0]))[:3]
        ]
        p["relative_lower_dimensions"] = [
            {"metric": m, "percentile": v}
            for m, v in sorted(available, key=lambda x: (x[1], x[0]))[:3]
        ]
    return profiles, dict(sorted(reference_sets.items()))
