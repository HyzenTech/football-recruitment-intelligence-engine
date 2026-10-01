"""Exact peer percentiles, coverage policy, transfer deduplication and artifact replay."""

from pathlib import Path

import pytest
from test_validation import ingested

from football_recruitment.config import load_settings
from football_recruitment.features.metrics import METRICS
from football_recruitment.features.pipeline import build_features
from football_recruitment.ingestion.storage import IngestionError, digest, json_bytes, strict_json
from football_recruitment.normalization.engine import build_profiles, percentile
from football_recruitment.normalization.pipeline import build_profile_artifacts, verify_profiles
from football_recruitment.validation.pipeline import validate_cohort


def settings():
    return load_settings(Path("config"))


def row(player, value, *, team="team:1", minutes=500.0, partial=False):
    return {
        "player_id": player,
        "player_name": player,
        "team_id": team,
        "team_name": team,
        "competition_id": "competition:1",
        "season_id": "season:1",
        "playing_seconds": minutes * 60,
        "denominator_minutes": minutes,
        "minutes_convention": "elapsed_including_stoppage",
        "appearances": 6,
        "excluded_appearances": int(partial),
        "partial_player_season": partial,
        "values": {
            m: {"value": value, "per90": value, "coverage": 1.0, "missing": 0} for m in METRICS
        },
    }


def calculate(rows, groups=None):
    roles = {(r["player_id"], r["team_id"]): {"CB": r["playing_seconds"]} for r in rows}
    return build_profiles(rows, groups or roles, settings())


def test_percentile_ties_lower_direction_and_constant():
    assert percentile(2, [1, 2, 2, 4]) == 50
    assert percentile(1, [1, 2, 2, 4]) == 12.5
    assert percentile(1, [1, 2, 2, 4], lower=True) == 87.5
    assert percentile(0, [0, 0]) is None
    with pytest.raises(IngestionError):
        percentile(float("nan"), [1, 2])


def test_exact_metric_and_category_scores_with_exposed_weights():
    profiles, refs = calculate([row(str(i), float(i)) for i in range(10)])
    p = profiles[0]
    assert p["metrics"]["passes_attempted"]["percentile"] == 5
    assert p["metrics"]["miscontrols"]["percentile"] == 95
    assert p["categories"]["progression"]["score"] == 5
    assert p["categories"]["retention"]["score"] == pytest.approx(65)
    assert p["categories"]["progression"]["weights"] == {
        "progressive_passes": 0.5,
        "progressive_carries": 0.5,
    }
    assert refs["CB:passes_attempted"]["peer_count"] == 10
    assert p["metrics"]["average_shot_distance"]["status"] == "DESCRIPTIVE_ONLY"
    assert "overall_score" not in p


def test_complete_common_population_does_not_reweight_missing_components():
    rows = [row(str(i), float(i)) for i in range(11)]
    rows[0]["values"]["progressive_passes"].update(value=None, per90=None, missing=1)
    profiles, refs = calculate(rows)
    assert profiles[0]["categories"]["progression"]["status"] == "MISSING_COMPONENT"
    assert refs["CB:progressive_passes+progressive_carries"]["peer_count"] == 10
    assert profiles[1]["categories"]["progression"]["score"] == 5
    assert profiles[1]["metrics"]["progressive_carries"]["peer_count"] == 11


def test_transfer_reference_keeps_one_largest_spell_per_player():
    rows = [row(str(i), float(i)) for i in range(10)] + [
        row("0", 100.0, team="team:2", minutes=600)
    ]
    profiles, refs = calculate(rows)
    assert len(profiles) == 11
    assert refs["CB:passes_attempted"]["peer_count"] == 10
    assert ["0", "team:2"] in refs["CB:passes_attempted"]["reference_ids"]
    assert ["0", "team:1"] not in refs["CB:passes_attempted"]["reference_ids"]


def test_partial_minutes_and_mixed_role_exclusions_are_explicit():
    rows = [row("partial", 1.0, partial=True), row("short", 1.0, minutes=449.99), row("mixed", 1.0)]
    roles = {(r["player_id"], r["team_id"]): {"CB": r["playing_seconds"]} for r in rows}
    roles["mixed", "team:1"] = {"CB": 15000.0, "FB": 15000.0}
    profiles, refs = calculate(rows, roles)
    assert [p["eligibility_reasons"] for p in profiles] == [
        ["PARTIAL_PLAYER_SEASON"],
        ["BELOW_MINIMUM_MINUTES"],
        ["MIXED_POSITION_USAGE"],
    ]
    assert not refs
    with pytest.raises(IngestionError, match="duration"):
        calculate(rows, {("mixed", "team:1"): {"CB": 1.0}})


def test_minimum_minutes_and_dominance_boundaries_are_inclusive():
    r = row("boundary", 1.0, minutes=450.0)
    profiles, _ = calculate([r], {("boundary", "team:1"): {"CB": 16200.0, "FB": 10800.0}})
    assert profiles[0]["peer_eligible"]
    assert profiles[0]["primary_position_group"] == "CB"
    assert profiles[0]["metrics"]["shots"]["status"] == "INSUFFICIENT_PEERS"


def test_constant_component_and_goalkeeper_scope():
    rows = [row(str(i), 0.0) for i in range(10)]
    profiles, _ = calculate(rows)
    assert profiles[0]["categories"]["shooting"]["status"] == "CONSTANT_COMPONENT"
    roles = {(r["player_id"], r["team_id"]): {"GK": r["playing_seconds"]} for r in rows}
    profiles, _ = calculate(rows, roles)
    assert profiles[0]["categories"]["shot_stopping"]["status"] == "UNSUPPORTED_DATA"
    assert profiles[0]["metrics"]["shots"]["status"] == "DESCRIPTIVE_ONLY"


def test_pipeline_determinism_replay_and_rehashed_tampering(tmp_path):
    config, canonical = ingested(tmp_path)
    minutes = validate_cohort(config, tmp_path, canonical)
    features = build_features(config, tmp_path, tmp_path / minutes["validation_manifest_path"])
    source = tmp_path / features["feature_manifest_path"]
    first = build_profile_artifacts(config, tmp_path, source)
    assert first == build_profile_artifacts(config, tmp_path, source)
    path = tmp_path / first["profile_manifest_path"]
    assert verify_profiles(config, tmp_path, path)["status"] == "VERIFIED"
    report = strict_json(path.read_bytes())
    artifact = report["artifacts"][0]
    table = path.parent.parent / artifact["path"]
    rows = [strict_json(line) for line in table.read_bytes().splitlines()]
    rows[0]["peer_eligible"] = True
    content = b"".join(json_bytes(r) for r in rows)
    table.write_bytes(content)
    artifact.update(sha256=digest(content), byte_count=len(content))
    content = json_bytes(report)
    changed = path.with_name(digest(content) + ".json")
    changed.write_bytes(content)
    with pytest.raises(IngestionError, match="replay"):
        verify_profiles(config, tmp_path, changed)


def test_profiles_reject_rehashed_false_partial_season_metadata(tmp_path):
    config, canonical = ingested(tmp_path)
    minutes = validate_cohort(config, tmp_path, canonical)
    features = build_features(config, tmp_path, tmp_path / minutes["validation_manifest_path"])
    path = tmp_path / features["feature_manifest_path"]
    report = strict_json(path.read_bytes())
    artifact = next(a for a in report["artifacts"] if a["kind"] == "player_team_season")
    table = path.parent.parent / artifact["path"]
    rows = [strict_json(line) for line in table.read_bytes().splitlines()]
    rows[0].update(excluded_appearances=1, partial_player_season=True)
    content = b"".join(json_bytes(r) for r in rows)
    table.write_bytes(content)
    artifact.update(sha256=digest(content), byte_count=len(content))
    content = json_bytes(report)
    changed = path.with_name(digest(content) + ".json")
    changed.write_bytes(content)
    with pytest.raises(IngestionError, match="Partial season flags"):
        build_profile_artifacts(config, tmp_path, changed)
