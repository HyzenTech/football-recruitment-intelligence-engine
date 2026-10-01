"""Similarity geometry, population selection, explanations and replay boundaries."""

from math import sqrt
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_validation import ingested

from football_recruitment.config import SimilaritySettings, load_settings
from football_recruitment.features.pipeline import build_features
from football_recruitment.ingestion.storage import IngestionError, digest, json_bytes, strict_json
from football_recruitment.normalization.pipeline import build_profile_artifacts
from football_recruitment.similarity.engine import find_similar_players, fit_scaler
from football_recruitment.similarity.evaluation import evaluate_similarity
from football_recruitment.similarity.pipeline import build_similarity, verify_similarity
from football_recruitment.validation.pipeline import validate_cohort


def settings():
    value = load_settings(Path("config"))
    return value.model_copy(
        update={"cohorts": value.cohorts.model_copy(update={"minimum_peer_count": 2})}
    )


def profile(player, x, y=0.0, *, team="team:1", role="CB", minutes=500.0, eligible=True):
    metrics = load_settings(Path("config")).similarity.features[role]
    return {
        "player_id": player,
        "player_name": player,
        "team_id": team,
        "team_name": team,
        "primary_position_group": role,
        "denominator_minutes": minutes,
        "peer_eligible": eligible,
        "eligibility_reasons": [] if eligible else ["PARTIAL_PLAYER_SEASON"],
        "metrics": {m: {"value": y if m == "long_passes" else x, "unit": "per90"} for m in metrics},
    }


def query(rows, **kwargs):
    return find_similar_players(
        rows, "query", "team:1", settings(), features=["passes_attempted", "long_passes"], **kwargs
    )


def test_exact_distance_score_contributions_and_query_excluded_scaling():
    result = query([profile("query", 0.0, 0.0), profile("a", 1.0, 1.0), profile("b", 3.0, 3.0)])
    assert result["scaler"]["passes_attempted"] == {"center": 2.0, "scale": 1.0, "status": "ACTIVE"}
    neighbor = result["neighbors"][0]
    assert neighbor["player_id"] == "a"
    assert neighbor["distance"] == sqrt(2)
    assert neighbor["similarity_score"] == pytest.approx(100 / (1 + sqrt(2)))
    assert sum(d["squared_contribution"] for d in neighbor["feature_differences"]) == 2
    assert sum(d["contribution_share"] for d in neighbor["feature_differences"]) == 1
    assert neighbor["key_differences"][0]["raw_difference"] == -1


def test_transfer_self_exclusion_deduplication_role_and_minutes_eligibility():
    rows = [
        profile("query", 0.0),
        profile("query", 100.0, team="team:2"),
        profile("a", 1.0, minutes=600.0),
        profile("a", 9.0, team="team:2"),
        profile("b", 3.0),
        profile("other_role", 0.0, role="ST"),
        profile("ineligible", 0.0, eligible=False),
    ]
    result = query(rows)
    assert result["reference_ids"] == [["a", "team:1"], ["b", "team:1"]]
    assert result["peer_count"] == 2
    assert result["warnings"] == ["ZERO_SCALE_FEATURES_OMITTED", "FEWER_NEIGHBORS_THAN_REQUESTED"]


def test_ties_are_deterministic_with_reordered_input():
    rows = [profile("query", 1.0), profile("b", 2.0), profile("a", 0.0)]
    first = query(rows)
    assert first == query(list(reversed(rows)))
    assert [n["player_id"] for n in first["neighbors"]] == ["a", "b"]


def test_missing_query_and_common_fixed_complete_peer_vectors():
    rows = [profile("query", 0.0), profile("a", 1.0), profile("b", 3.0), profile("missing", 2.0)]
    rows[-1]["metrics"]["long_passes"]["value"] = None
    result = query(rows)
    assert result["excluded_incomplete_peers"] == 1
    assert result["peer_count"] == 2
    rows[0]["metrics"]["passes_attempted"]["value"] = None
    assert query(rows)["status"] == "MISSING_QUERY_FEATURES"


def test_constant_features_and_insufficient_peers_are_suppressed():
    assert (
        query([profile("query", 2.0), profile("a", 1.0), profile("b", 1.0)])["status"]
        == "NO_VARIABLE_FEATURES"
    )
    assert query([profile("query", 0.0), profile("a", 1.0)])["status"] == "INSUFFICIENT_PEERS"
    assert query([profile("query", 0.0, eligible=False)])["status"] == "INELIGIBLE_QUERY"


def test_robust_scaler_uses_linear_quartiles_and_reports_zero_iqr():
    rows = [profile(str(i), float(i)) for i in range(5)]
    scaler = fit_scaler(rows, ["passes_attempted", "long_passes"], "robust")
    assert scaler["passes_attempted"]["center"] == 2.0
    assert scaler["passes_attempted"]["scale"] == 2.0
    assert scaler["long_passes"]["status"] == "ZERO_SCALE"


@pytest.mark.parametrize("top_k", [0, 51, True, 1.5])
def test_invalid_top_k_is_rejected(top_k):
    with pytest.raises(IngestionError, match="top_k"):
        query([profile("query", 1.0)], top_k=top_k)


def test_unknown_query_position_and_nonfinite_values_fail():
    rows = [profile("query", 1.0), profile("a", 1.0), profile("b", 2.0)]
    with pytest.raises(IngestionError, match="position"):
        query(rows, position_group="ST")
    with pytest.raises(IngestionError, match="does not exist"):
        find_similar_players(rows, "absent", "team:1", settings())
    rows[0]["metrics"]["passes_attempted"]["value"] = float("nan")
    with pytest.raises(IngestionError, match="finite"):
        query(rows)


def test_similarity_config_rejects_unknown_features_and_goalkeeper_outfield_metrics():
    data = load_settings(Path("config")).similarity.model_dump()
    for group, metric in (("CB", "invented"), ("GK", "shots")):
        features = dict(data["features"])
        features[group] = (metric,)
        with pytest.raises(ValidationError):
            SimilaritySettings.model_validate(data | {"features": features})


def test_sensitivity_experiments_are_deterministic_and_label_unavailable_queries():
    rows = [profile("query", 1.0)] + [profile(str(i), float(i)) for i in range(10)]
    baseline = [find_similar_players(rows, "query", "team:1", settings())]
    first = evaluate_similarity(rows, settings(), baseline)
    assert first == evaluate_similarity(rows, settings(), baseline)
    assert len(first["scenarios"]) == 9
    minute600 = next(s for s in first["scenarios"] if s["scenario"] == "minimum_minutes_600")
    assert minute600["queries_remaining_available"] == 0
    assert minute600["mean_top5_overlap"] is None


def test_pipeline_determinism_and_rehashed_artifact_tampering(tmp_path):
    config, canonical = ingested(tmp_path)
    minutes = validate_cohort(config, tmp_path, canonical)
    features = build_features(config, tmp_path, tmp_path / minutes["validation_manifest_path"])
    profiles = build_profile_artifacts(
        config, tmp_path, tmp_path / features["feature_manifest_path"]
    )
    source = tmp_path / profiles["profile_manifest_path"]
    first = build_similarity(config, tmp_path, source)
    assert first == build_similarity(config, tmp_path, source)
    path = tmp_path / first["similarity_manifest_path"]
    assert verify_similarity(config, tmp_path, path)["status"] == "VERIFIED"
    report = strict_json(path.read_bytes())
    artifact = report["artifacts"][0]
    table = path.parent.parent / artifact["path"]
    rows = [strict_json(line) for line in table.read_bytes().splitlines()]
    rows[0]["status"] = "AVAILABLE"
    content = b"".join(json_bytes(r) for r in rows)
    table.write_bytes(content)
    artifact.update(sha256=digest(content), byte_count=len(content))
    content = json_bytes(report)
    changed = path.with_name(digest(content) + ".json")
    changed.write_bytes(content)
    with pytest.raises(IngestionError, match="replay"):
        verify_similarity(config, tmp_path, changed)
