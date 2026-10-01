import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from football_recruitment.evaluation.review import check_reviews


@pytest.fixture
def records():
    player = {"player_id": "player:1", "team_id": "team:1"}
    evidence = {
        "protocol_version": "cb-review-0.1",
        "pairs": [],
        "candidates": [{"case_id": "RANK-01", "player": player}],
        "footage_locators": [{"player": player, "match_id": f"match:{i}"} for i in (1, 2)],
    }
    source = player | {
        "source_id": "S1",
        "match_id": "match:1",
        "reference": "licensed:file:one",
        "authorization_basis": "Reviewer's licensed access declaration",
        "observed_role": "Centre back",
        "content_kind": "full_match",
        "observed_intervals_seconds": [[0, 3600]],
    }
    row = {
        "review_status": "COMPLETED",
        "reviewer": "Test reviewer",
        "reviewer_experience": "Synthetic fixture only",
        "review_date": "2026-10-01",
        "model_seen_before_review": True,
        "footage_sources_and_timestamps": [source],
        "observation_summary": "Supporting and contradictory notes [S1] [S2]",
        "context_and_uncertainty": "Synthetic fixture; confidence basis recorded here",
        "supported_next_action": "Collect fresh cases",
        "confidence_low_medium_high": "low",
        "blind_requirement_fit_1_to_5": 3,
        "revealed_model_agreement_1_to_5": 3,
        "disagreement_reason": "Mixed contextual support",
    }
    return evidence, {"CASE-01": row}


def test_substantial_coverage_is_advisory_and_does_not_certify_expertise(records):
    evidence, results = records
    before = copy.deepcopy(results)
    report = check_reviews(evidence, results)
    assert results == before
    assert report["valid_structure"]
    assert report["cases"][0]["warnings"]
    second = results["CASE-01"]["footage_sources_and_timestamps"][0].copy()
    second.update(source_id="S2", match_id="match:2", reference="licensed:file:two")
    results["CASE-01"]["footage_sources_and_timestamps"].append(second)
    assert not check_reviews(evidence, results)["cases"][0]["warnings"]
    assert report["expert_validation"] == "NOT_CERTIFIED"
    assert report["predictive_validation"] == "NOT_PERFORMED"


def test_overlaps_and_duplicate_editions_cannot_inflate_exposure(records):
    evidence, results = records
    sources = results["CASE-01"]["footage_sources_and_timestamps"]
    sources[0]["observed_intervals_seconds"] = [[0, 1800], [900, 2700], [0, 1800]]
    sources.append(sources[0] | {"source_id": "S2", "reference": "second edition"})
    report = check_reviews(evidence, results)
    assert report["valid_structure"]
    minutes = report["cases"][0]["coverage"][0]["self_reported_full_match_minutes"]
    assert minutes == {"match:1": 45}


@pytest.mark.parametrize(
    "change",
    [
        {"blind_requirement_fit_1_to_5": True},
        {"blind_requirement_fit_1_to_5": 6},
        {"blind_pair_similarity_1_to_5": 3},
        {"model_seen_before_review": "yes"},
        {"review_date": "20261001"},
        {"review_status": "NOT_PERFORMED"},
        {"review_status": "NOT_ASSESSABLE"},
        {"footage_sources_and_timestamps": []},
        {"observation_summary": "No source citations"},
    ],
)
def test_unsupported_or_inconsistent_ratings_are_rejected(records, change):
    evidence, results = records
    results["CASE-01"].update(change)
    assert not check_reviews(evidence, results)["valid_structure"]


@pytest.mark.parametrize(
    "change",
    [
        {"player_id": "wrong player"},
        {"match_id": "wrong fixture"},
        {"authorization_basis": ""},
        {"observed_intervals_seconds": [[0, float("nan")]]},
        {"observed_intervals_seconds": [[30, 10]]},
    ],
)
def test_bad_sources_are_rejected(records, change):
    evidence, results = records
    results["CASE-01"]["footage_sources_and_timestamps"][0].update(change)
    assert not check_reviews(evidence, results)["valid_structure"]


def test_highlights_are_not_full_match_coverage(records):
    evidence, results = records
    results["CASE-01"]["footage_sources_and_timestamps"][0]["content_kind"] = "highlights"
    report = check_reviews(evidence, results)
    assert report["valid_structure"]
    assert len(report["cases"][0]["warnings"]) == 2
    assert report["cases"][0]["coverage"][0]["self_reported_full_match_minutes"] == {"match:1": 0}


def test_pair_requires_viewing_for_both_players(records):
    evidence, results = records
    player = evidence["candidates"].pop()["player"]
    evidence["pairs"] = [
        {
            "case_id": "SIM-01",
            "query": player,
            "peer": {"player_id": "player:2", "team_id": "team:2"},
        }
    ]
    results["CASE-01"].pop("blind_requirement_fit_1_to_5")
    results["CASE-01"]["blind_pair_similarity_1_to_5"] = 3
    assert any(
        "player:2" in issue for issue in check_reviews(evidence, results)["cases"][0]["errors"]
    )


def test_missing_and_unknown_cases_are_rejected(records):
    evidence, _ = records
    report = check_reviews(evidence, {"OTHER": {}})
    assert not report["valid_structure"]
    assert report["errors"] and report["cases"][0]["errors"]


@pytest.fixture
def sampled_records(records):
    evidence, results = records
    row = results["CASE-01"]
    row.update(
        review_status="LIMITED",
        confidence_low_medium_high="unknown",
        blind_requirement_fit_1_to_5=None,
        revealed_model_agreement_1_to_5=None,
    )
    source = row["footage_sources_and_timestamps"][0]
    source.update(
        viewing_mode="sampled_with_skips",
        timestamp_basis="youtube_replay",
        watched_minutes="unknown",
        observed_intervals_seconds=[],
        observed_role="unknown",
        authorization_basis="unknown",
        timestamped_observations=[
            {
                "timestamp": "1:02:32",
                "replay_seconds": 3752,
                "match_clock": None,
                "observation": "Good interception.",
            }
        ],
    )
    return evidence, results


def test_skipped_sample_preserves_unknowns_without_inventing_duration(sampled_records):
    evidence, results = sampled_records
    before = copy.deepcopy(results)
    report = check_reviews(evidence, results)
    assert results == before
    assert report["valid_structure"]
    coverage = report["cases"][0]["coverage"][0]
    assert coverage["self_reported_full_match_minutes"] == {}
    assert coverage["continuous_duration_status"] == "unknown"
    assert coverage["timestamped_sample_present"]
    assert any("continuous duration unknown" in w for w in report["cases"][0]["warnings"])


@pytest.mark.parametrize(
    "change",
    [
        {"review_status": "COMPLETED"},
        {"blind_requirement_fit_1_to_5": 3},
        {"revealed_model_agreement_1_to_5": 3},
    ],
)
def test_skipped_sample_cannot_be_promoted_to_completion_or_ratings(sampled_records, change):
    evidence, results = sampled_records
    results["CASE-01"].update(change)
    assert not check_reviews(evidence, results)["valid_structure"]


@pytest.mark.parametrize(
    "change",
    [
        {"replay_seconds": 3753},
        {"timestamp": "1:62:32"},
        {"match_clock": "56:42"},
        {"observation": ""},
        {"replay_seconds": True},
    ],
)
def test_point_references_cannot_fabricate_clocks_or_mismatch_replay_time(sampled_records, change):
    evidence, results = sampled_records
    results["CASE-01"]["footage_sources_and_timestamps"][0]["timestamped_observations"][0].update(
        change
    )
    assert not check_reviews(evidence, results)["valid_structure"]


def test_empty_or_unreferenced_sample_is_rejected(sampled_records):
    evidence, results = sampled_records
    results["CASE-01"]["observation_summary"] = "No source citation"
    assert not check_reviews(evidence, results)["valid_structure"]
    results["CASE-01"]["observation_summary"] = "Sample notes [S1]"
    results["CASE-01"]["footage_sources_and_timestamps"][0]["timestamped_observations"] = []
    assert not check_reviews(evidence, results)["valid_structure"]


def test_qualified_exposure_disclosure_is_not_forced_into_absolute_blinding(sampled_records):
    evidence, results = sampled_records
    row = results["CASE-01"]
    row.update(
        model_seen_before_review="unknown",
        model_exposure_disclosure="No deliberate exposure before completing notes.",
    )
    report = check_reviews(evidence, results)
    assert report["valid_structure"]
    assert any("Prior model exposure unknown" in w for w in report["cases"][0]["warnings"])
    row.pop("model_exposure_disclosure")
    assert not check_reviews(evidence, results)["valid_structure"]


def test_cli_reads_blank_pack_without_writing_and_rejects_duplicate_json(records, tmp_path):
    evidence, _ = records
    (tmp_path / "MODEL_EVIDENCE.json").write_text(json.dumps(evidence), encoding="utf-8")
    path = tmp_path / "REVIEW_RESULTS.json"
    path.write_text(
        json.dumps(
            {"CASE-01": {"review_status": "NOT_PERFORMED", "footage_sources_and_timestamps": []}}
        ),
        encoding="utf-8",
    )
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "scripts/check_review_records.py"),
        "--pack-dir",
        str(tmp_path),
    ]
    run = subprocess.run(command, capture_output=True, text=True, check=False)
    assert run.returncode == 0
    assert json.loads(run.stdout)["pending_cases"] == 1
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    path.write_text('{"CASE-01": {}, "CASE-01": {}}', encoding="utf-8")
    run = subprocess.run(command, capture_output=True, text=True, check=False)
    assert run.returncode == 2
    assert "Duplicate" in json.loads(run.stdout)["error"]
