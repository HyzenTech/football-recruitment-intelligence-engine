"""Deterministic nearest neighbors with query-excluded scaling and fixed complete vectors."""

from math import isfinite, sqrt
from statistics import fmean, median

from football_recruitment.ingestion.storage import IngestionError

SIMILARITY_VERSION = "similarity-0.6.0"


def quantile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def fit_scaler(peers, features, method):
    if method not in {"standard", "robust"}:
        raise IngestionError("Unknown similarity scaling method")
    scales = {}
    for metric in features:
        values = [p["metrics"][metric]["value"] for p in peers]
        center = fmean(values) if method == "standard" else median(values)
        scale = (
            sqrt(fmean((v - center) ** 2 for v in values))
            if method == "standard"
            else quantile(values, 0.75) - quantile(values, 0.25)
        )
        if not isfinite(center) or not isfinite(scale):
            raise IngestionError("Similarity scaler overflow")
        scales[metric] = {
            "center": center,
            "scale": scale,
            "status": "ACTIVE" if scale > 0 else "ZERO_SCALE",
        }
    return scales


def find_similar_players(
    profiles,
    player_id,
    team_id,
    settings,
    *,
    position_group=None,
    top_k=None,
    features=None,
    scaling=None,
    reference_player_ids=None,
):
    """Return within-role neighbors; the caller supplies verified canonical-derived profiles."""
    top_k = settings.similarity.default_top_k if top_k is None else top_k
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 50:
        raise IngestionError("top_k must be an integer from 1 to 50")
    rows = {(p["player_id"], p["team_id"]): p for p in profiles}
    if len(rows) != len(profiles):
        raise IngestionError("Duplicate similarity profile identity")
    query = rows.get((player_id, team_id))
    if query is None:
        raise IngestionError("Query player/team profile does not exist")
    group = query["primary_position_group"]
    if position_group is not None and position_group != group:
        raise IngestionError("Query position does not match validated primary group")
    method = scaling or settings.similarity.scaling
    if method not in {"standard", "robust"}:
        raise IngestionError("Unknown similarity scaling method")
    configured = list(settings.similarity.features[group]) if group else []
    selected = configured if features is None else list(features)
    if features is not None and (
        not selected or len(set(selected)) != len(selected) or not set(selected) <= set(configured)
    ):
        raise IngestionError("Similarity ablations must be nonempty subsets of configured features")
    result = {
        "similarity_version": SIMILARITY_VERSION,
        "query": {
            k: query[k]
            for k in ("player_id", "player_name", "team_id", "team_name", "denominator_minutes")
        },
        "position_group": group,
        "top_k": top_k,
        "features": selected,
        "scaling_method": method,
        "minimum_peer_count": settings.cohorts.minimum_peer_count,
        "reference_ids": [],
        "peer_count": 0,
        "excluded_incomplete_peers": 0,
        "scaler": {},
        "active_features": [],
        "neighbors": [],
        "warnings": [],
        "distance_formula": "sqrt(sum(((query_value-peer_value)/scale)**2))",
        "score_formula": "100/(1+distance)",
    }
    if not query["peer_eligible"]:
        return result | {
            "status": "INELIGIBLE_QUERY",
            "eligibility_reasons": query["eligibility_reasons"],
        }

    def complete(profile):
        for metric in selected:
            value = profile["metrics"][metric]["value"]
            if value is None:
                return False
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise IngestionError("Similarity requires finite numeric features")
        return True

    if not complete(query):
        return result | {
            "status": "MISSING_QUERY_FEATURES",
            "missing_features": [m for m in selected if query["metrics"][m]["value"] is None],
        }
    spells = {}
    for p in profiles:
        if (
            not p["peer_eligible"]
            or p["primary_position_group"] != group
            or p["player_id"] == player_id
        ):
            continue
        if reference_player_ids is not None and p["player_id"] not in reference_player_ids:
            continue
        old = spells.get(p["player_id"])
        if old is None or (-p["denominator_minutes"], p["team_id"]) < (
            -old["denominator_minutes"],
            old["team_id"],
        ):
            spells[p["player_id"]] = p
    peers = [
        p
        for p in sorted(spells.values(), key=lambda p: (p["player_id"], p["team_id"]))
        if complete(p)
    ]
    result.update(
        peer_count=len(peers),
        excluded_incomplete_peers=len(spells) - len(peers),
        reference_ids=[[p["player_id"], p["team_id"]] for p in peers],
    )
    if len(peers) < settings.cohorts.minimum_peer_count:
        return result | {"status": "INSUFFICIENT_PEERS"}
    scales = fit_scaler(peers, selected, method)
    active = [m for m in selected if scales[m]["status"] == "ACTIVE"]
    result.update(scaler=scales, active_features=active)
    if len(active) < len(selected):
        result["warnings"].append("ZERO_SCALE_FEATURES_OMITTED")
    if not active:
        return result | {"status": "NO_VARIABLE_FEATURES"}
    neighbors = []
    for p in peers:
        differences = []
        for metric in active:
            qv, pv = query["metrics"][metric]["value"], p["metrics"][metric]["value"]
            delta = (qv - pv) / scales[metric]["scale"]
            differences.append(
                {
                    "metric": metric,
                    "unit": query["metrics"][metric]["unit"],
                    "query_value": qv,
                    "peer_value": pv,
                    "raw_difference": qv - pv,
                    "standardized_difference": delta,
                    "squared_contribution": delta**2,
                }
            )
        squared = sum(d["squared_contribution"] for d in differences)
        distance = sqrt(squared)
        if not isfinite(distance):
            raise IngestionError("Similarity distance overflow")
        for d in differences:
            d["contribution_share"] = d["squared_contribution"] / squared if squared else 0.0
        neighbors.append(
            {
                **{
                    k: p[k]
                    for k in (
                        "player_id",
                        "player_name",
                        "team_id",
                        "team_name",
                        "denominator_minutes",
                    )
                },
                "distance": distance,
                "similarity_score": 100 / (1 + distance),
                "feature_differences": differences,
                "key_similarities": sorted(
                    differences, key=lambda d: (abs(d["standardized_difference"]), d["metric"])
                )[:3],
                "key_differences": sorted(
                    differences, key=lambda d: (-abs(d["standardized_difference"]), d["metric"])
                )[:3],
            }
        )
    result["neighbors"] = sorted(
        neighbors, key=lambda n: (n["distance"], n["player_id"], n["team_id"])
    )[:top_k]
    if len(peers) < top_k:
        result["warnings"].append("FEWER_NEIGHBORS_THAN_REQUESTED")
    return result | {"status": "AVAILABLE"}


def all_queries(profiles, settings):
    return [
        find_similar_players(profiles, p["player_id"], p["team_id"], settings)
        for p in sorted(profiles, key=lambda p: (p["player_id"], p["team_id"]))
    ]
