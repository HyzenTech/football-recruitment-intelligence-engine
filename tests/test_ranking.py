"""Exact weighted common-population rankings, filters, exclusions and replay."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from test_validation import ingested

from football_recruitment.config import RankingRequirement, load_settings
from football_recruitment.features.pipeline import build_features
from football_recruitment.ingestion.storage import IngestionError, digest, json_bytes, strict_json
from football_recruitment.normalization.pipeline import build_profile_artifacts
from football_recruitment.ranking.engine import build_rankings, evaluate_rankings, rank_players
from football_recruitment.ranking.pipeline import build_ranking_artifacts, verify_rankings
from football_recruitment.validation.pipeline import validate_cohort


def settings():
    config = load_settings(Path("config"))
    return config.model_copy(
        update={"cohorts": config.cohorts.model_copy(update={"minimum_peer_count": 2})}
    )


def requirement(**kwargs):
    return RankingRequirement.model_validate(
        {
            "name": "Synthetic activity",
            "position_group": "CB",
            "weights": {"passes_attempted": 3.0, "miscontrols": 1.0},
        }
        | kwargs
    )


def profile(player, value, *, team="team:1", minutes=500.0, eligible=True, role="CB"):
    return {
        "player_id": player,
        "player_name": player,
        "team_id": team,
        "team_name": team,
        "denominator_minutes": minutes,
        "primary_position_group": role,
        "peer_eligible": eligible,
        "eligibility_reasons": [] if eligible else ["PARTIAL_PLAYER_SEASON"],
        "metrics": {
            m: {"value": value, "unit": "per90", "coverage": 1.0}
            for m in ("passes_attempted", "miscontrols", "shots")
        },
    }


def test_exact_directional_percentiles_weights_and_component_sum():
    result = rank_players([profile("a", 1.0), profile("b", 3.0)], requirement(), settings())
    assert result["normalized_weights"] == {"miscontrols": 0.25, "passes_attempted": 0.75}
    first = result["rankings"][0]
    assert first["player_id"] == "b" and first["recruitment_score"] == 62.5
    assert first["components"]["miscontrols"]["percentile"] == 25
    assert first["components"]["passes_attempted"]["percentile"] == 75
    assert sum(v["contribution"] for v in first["components"].values()) == 62.5
    assert first["weaker_dimensions"][0]["metric"] == "miscontrols"


def test_common_population_missing_feature_excludes_entire_player():
    rows = [profile("a", 1.0), profile("b", 3.0), profile("missing", 2.0)]
    rows[-1]["metrics"]["miscontrols"]["value"] = None
    result = rank_players(rows, requirement(), settings())
    assert result["peer_count"] == 2
    assert result["rankings"][0]["components"]["passes_attempted"]["percentile"] == 75
    assert result["exclusions"][0]["reasons"] == ["MISSING_REQUIRED_METRICS"]


def test_zero_weight_missing_metric_does_not_change_eligibility():
    rows = [profile("a", 1.0), profile("b", 3.0)]
    rows[0]["metrics"]["shots"]["value"] = None
    r = requirement(weights={"passes_attempted": 1.0, "shots": 0.0})
    result = rank_players(rows, r, settings())
    assert result["peer_count"] == 2 and result["ignored_zero_weight_metrics"] == ["shots"]


def test_filters_leave_reference_population_and_percentiles_unchanged():
    rows = [profile("a", 1.0, minutes=700.0), profile("b", 3.0, minutes=500.0)]
    result = rank_players(rows, requirement(minimum_minutes=600.0), settings())
    assert result["peer_count"] == 2 and result["candidate_count"] == 1
    assert result["rankings"][0]["recruitment_score"] == 37.5
    excluded = rank_players(rows, requirement(excluded_team_ids=("team:1",)), settings())
    assert excluded["status"] == "NO_CANDIDATES" and excluded["peer_count"] == 2
    with pytest.raises(IngestionError, match="cannot lower"):
        rank_players(rows, requirement(minimum_minutes=300.0), settings())


def test_transfer_deduplication_ineligible_role_exclusion_and_determinism():
    rows = [
        profile("a", 1.0),
        profile("a", 10.0, team="team:2", minutes=600.0),
        profile("b", 3.0),
        profile("partial", 1.0, eligible=False),
        profile("other", 1.0, role="ST"),
    ]
    first = rank_players(rows, requirement(), settings())
    assert first == rank_players(list(reversed(rows)), requirement(), settings())
    assert first["reference_ids"] == [["a", "team:2"], ["b", "team:1"]]
    assert len(first["exclusions"]) == 3


def test_tie_order_top_k_and_large_weight_normalization():
    rows = [profile("b", 3.0), profile("a", 1.0)]
    r = requirement(weights={"passes_attempted": 1e308, "miscontrols": 1e308}, top_k=1)
    result = rank_players(rows, r, settings())
    assert result["rankings"][0]["player_id"] == "a"
    assert result["rankings"][0]["rank"] == 1 and result["candidate_count"] == 2


def test_constant_component_and_small_peer_groups_suppress_score():
    assert (
        rank_players([profile("a", 1.0)], requirement(), settings())["status"]
        == "INSUFFICIENT_PEERS"
    )
    assert (
        rank_players([profile("a", 1.0), profile("b", 1.0)], requirement(), settings())["status"]
        == "CONSTANT_COMPONENT"
    )


@pytest.mark.parametrize(
    "weights",
    [
        {},
        {"passes_attempted": 0.0},
        {"passes_attempted": -1.0},
        {"invented": 1.0},
        {"average_shot_distance": 1.0},
        {"passes_attempted": float("nan")},
        {"passes_attempted": float("inf")},
        {"passes_attempted": True},
    ],
)
def test_invalid_weights_fail(weights):
    with pytest.raises(ValidationError):
        requirement(weights=weights)


@pytest.mark.parametrize(
    "field,value",
    [
        ("maximum_age", 23),
        ("maximum_market_value", 1000000),
        ("contract_expiry_before", "2027-06-30"),
    ],
)
def test_unsupported_filters_fail_instead_of_ignoring(field, value):
    with pytest.raises(ValidationError):
        requirement(**{field: value})


def test_goalkeeper_outfield_requirement_is_rejected():
    with pytest.raises(ValidationError, match="distribution"):
        requirement(position_group="GK", weights={"shots": 1.0})


def test_sensitivity_is_deterministic_and_uses_named_weights():
    config = settings()
    config = config.model_copy(
        update={
            "ranking": config.ranking.model_copy(
                update={"requirements": {"synthetic": requirement()}}
            )
        }
    )
    rows = [profile("a", 1.0), profile("b", 3.0)]
    base = build_rankings(rows, config)
    evaluation = evaluate_rankings(rows, config, base)
    assert evaluation == evaluate_rankings(rows, config, base)
    assert len(evaluation["scenarios"]) == 3
    assert evaluation["scenarios"][0]["variant_status"] == "NO_CANDIDATES"


def test_ranking_artifact_determinism_and_rehashed_tampering(tmp_path):
    config, canonical = ingested(tmp_path)
    minutes = validate_cohort(config, tmp_path, canonical)
    features = build_features(config, tmp_path, tmp_path / minutes["validation_manifest_path"])
    profiles = build_profile_artifacts(
        config, tmp_path, tmp_path / features["feature_manifest_path"]
    )
    source = tmp_path / profiles["profile_manifest_path"]
    first = build_ranking_artifacts(config, tmp_path, source)
    assert first == build_ranking_artifacts(config, tmp_path, source)
    path = tmp_path / first["ranking_manifest_path"]
    assert verify_rankings(config, tmp_path, path)["status"] == "VERIFIED"
    report = strict_json(path.read_bytes())
    artifact = report["artifacts"][0]
    table = path.parent.parent / artifact["path"]
    rankings = strict_json(table.read_bytes())
    next(iter(rankings.values()))["status"] = "AVAILABLE"
    data = json_bytes(rankings)
    table.write_bytes(data)
    artifact.update(sha256=digest(data), byte_count=len(data))
    data = json_bytes(report)
    changed = path.with_name(digest(data) + ".json")
    changed.write_bytes(data)
    with pytest.raises(IngestionError, match="replay"):
        verify_rankings(config, tmp_path, changed)
