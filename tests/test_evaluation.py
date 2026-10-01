"""Repeated cohort perturbations, invariance, honest availability and replay."""

from copy import deepcopy

import pytest
from test_ranking import profile, requirement, settings
from test_validation import ingested

from football_recruitment.domain.models import PositionGroup
from football_recruitment.evaluation.engine import (
    audit_results,
    distribution,
    evaluate_cohort,
    retained_players,
)
from football_recruitment.evaluation.pipeline import build_evaluation, verify_evaluation
from football_recruitment.features.pipeline import build_features
from football_recruitment.ingestion.storage import IngestionError, digest, json_bytes, strict_json
from football_recruitment.normalization.pipeline import build_profile_artifacts
from football_recruitment.ranking.engine import build_rankings
from football_recruitment.similarity.engine import all_queries
from football_recruitment.validation.pipeline import validate_cohort


def configured():
    config = settings()
    features = dict(config.similarity.features)
    features[PositionGroup.CB] = ("passes_attempted", "long_passes")
    return config.model_copy(
        update={
            "similarity": config.similarity.model_copy(update={"features": features}),
            "ranking": config.ranking.model_copy(
                update={"requirements": {"synthetic": requirement()}}
            ),
        }
    )


def rows():
    result = [profile(str(i), float(i)) for i in range(12)]
    for i, p in enumerate(result):
        p["metrics"]["long_passes"] = {"value": float(i * i), "unit": "per90", "coverage": 1.0}
    return result


def test_hash_sampling_is_order_independent_and_keeps_spells_together():
    profiles = rows() + [profile("0", 1.0, team="team:2")]
    assert retained_players(profiles, 1) == retained_players(list(reversed(profiles)), 1)
    assert retained_players(profiles, 1) <= set(p["player_id"] for p in profiles)
    assert retained_players(profiles, 1) != retained_players(profiles, 2)


def test_repeated_results_and_summaries_are_deterministic():
    profiles = rows()
    config = configured()
    first = evaluate_cohort(profiles, config, 3)
    assert first == evaluate_cohort(list(reversed(profiles)), config, 3)
    assert len(first["similarity_records"]) == 36
    assert len(first["ranking_records"]) == 3
    assert first["combined_checks"]["status"] == "PASS"
    assert first["football_review"]["predictive_validation"] == "NOT_PERFORMED"


def test_positive_unit_changes_preserve_neighbors_and_rank_percentiles():
    profiles = rows()
    config = configured()
    changed = deepcopy(profiles)
    for p in changed:
        for metric in p["metrics"].values():
            metric["value"] = 5 * metric["value"] + 7
    a, b = all_queries(profiles, config), all_queries(changed, config)
    for x, y in zip(a, b, strict=True):
        assert [n["player_id"] for n in x["neighbors"]] == [n["player_id"] for n in y["neighbors"]]
        assert [n["distance"] for n in x["neighbors"]] == pytest.approx(
            [n["distance"] for n in y["neighbors"]]
        )
    ra, rb = build_rankings(profiles, config), build_rankings(changed, config)
    assert [r["recruitment_score"] for r in ra["synthetic"]["rankings"]] == [
        r["recruitment_score"] for r in rb["synthetic"]["rankings"]
    ]


def test_unavailable_attempts_remain_counted_and_have_null_overlap():
    config = configured()
    config = config.model_copy(
        update={"cohorts": config.cohorts.model_copy(update={"minimum_peer_count": 10})}
    )
    result = evaluate_cohort(rows(), config, 10)
    summary = result["similarity_stability"]["CB"]
    assert sum(summary["status_counts"].values()) == 120
    assert summary["status_counts"]["INSUFFICIENT_PEERS"] > 0
    assert summary["top5_overlap"]["count"] == summary["status_counts"].get("AVAILABLE", 0)
    assert all(
        r["top5_overlap"] is None
        for r in result["similarity_records"]
        if r["status"] != "AVAILABLE"
    )


def test_combined_audit_rejects_self_match_and_incorrect_contributions():
    profiles = rows()
    config = configured()
    sim = all_queries(profiles, config)
    rank = build_rankings(profiles, config)
    changed = deepcopy(sim)
    changed[0]["neighbors"][0]["player_id"] = changed[0]["query"]["player_id"]
    with pytest.raises(IngestionError, match="self-exclusion"):
        audit_results(profiles, changed, rank)
    changed = deepcopy(rank)
    changed["synthetic"]["rankings"][0]["components"]["passes_attempted"]["contribution"] += 1
    with pytest.raises(IngestionError, match="contributions"):
        audit_results(profiles, sim, changed)


@pytest.mark.parametrize("replicates", [1, 101, True, 2.5])
def test_invalid_replicate_counts_fail(replicates):
    with pytest.raises(IngestionError, match="replicates"):
        evaluate_cohort(rows(), configured(), replicates)


def test_distribution_handles_no_available_values():
    assert distribution([]) == {"count": 0, "mean": None, "minimum": None, "maximum": None}
    assert distribution([0.2, 0.8])["mean"] == 0.5


def test_evaluation_artifact_replay_rejects_rehashed_false_claim(tmp_path):
    config, canonical = ingested(tmp_path)
    minutes = validate_cohort(config, tmp_path, canonical)
    features = build_features(config, tmp_path, tmp_path / minutes["validation_manifest_path"])
    profiles = build_profile_artifacts(
        config, tmp_path, tmp_path / features["feature_manifest_path"]
    )
    source = tmp_path / profiles["profile_manifest_path"]
    first = build_evaluation(config, tmp_path, source, replicates=2)
    assert first == build_evaluation(config, tmp_path, source, replicates=2)
    path = tmp_path / first["evaluation_manifest_path"]
    assert verify_evaluation(config, tmp_path, path)["status"] == "VERIFIED"
    manifest = strict_json(path.read_bytes())
    artifact = manifest["artifacts"][0]
    table = path.parent.parent / artifact["path"]
    report = strict_json(table.read_bytes())
    report["football_review"]["predictive_validation"] = "PASS"
    data = json_bytes(report)
    table.write_bytes(data)
    artifact.update(sha256=digest(data), byte_count=len(data))
    data = json_bytes(manifest)
    changed = path.with_name(digest(data) + ".json")
    changed.write_bytes(data)
    with pytest.raises(IngestionError, match="replay"):
        verify_evaluation(config, tmp_path, changed)
