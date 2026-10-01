"""Exact feature definitions, missingness, aggregation and lineage boundaries."""

import json
from pathlib import Path

import pytest
from test_ingestion import configured, fake_fetcher
from test_minutes import event
from test_validation import complete_payloads, ingested

from football_recruitment.config import load_settings
from football_recruitment.domain.models import CarryDetail, Location, PassDetail, ShotDetail
from football_recruitment.features.metrics import (
    accumulate_event,
    aggregate_statistics,
    empty_statistics,
    progressive,
    values,
)
from football_recruitment.features.pipeline import build_features
from football_recruitment.features.verification import verify_features
from football_recruitment.ingestion.pipeline import ingest_cohort
from football_recruitment.ingestion.storage import IngestionError, digest, json_bytes
from football_recruitment.validation.pipeline import validate_cohort

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = load_settings(ROOT / "config")


def location(x, y=40):
    return Location(x=float(x / 120), y=float(y / 80))


def pass_event(outcome="complete", start=60, end=100, **extra):
    return event(
        "Pass",
        seconds=100,
        player=101,
        play_pattern="Regular Play",
        start_location=location(start),
        detail=PassDetail(
            outcome=outcome,
            end_location=location(end),
            switch=False,
            cross=False,
            length_provider_units=float(abs(end - start)),
            **extra,
        ),
    )


def stats_for(events, lookup=None, eligible=None):
    stats = empty_statistics()
    issues = []
    used = set()
    for e in events:
        accumulate_event(stats, e, SETTINGS.metrics, lookup or {}, eligible or set(), used, issues)
    return stats, issues


def test_progression_and_zone_exact_boundaries():
    assert progressive((60, 40), (75, 40), SETTINGS.metrics)
    assert not progressive((60, 40), (74.99, 40), SETTINGS.metrics)
    assert not progressive((120, 40), (120, 40), SETTINGS.metrics)
    assert not progressive((100, 40), (90, 40), SETTINGS.metrics)
    assert progressive(None, (100, 40), SETTINGS.metrics) is None
    stats, _ = stats_for([pass_event(start=79, end=80), pass_event(start=80, end=102)])
    r = values(stats, 90)
    assert r["passes_into_final_third"]["value"] == 1
    assert r["passes_into_box"]["value"] == 1


def test_unknown_pass_outcome_preserves_attempts_but_suppresses_completion():
    stats, _ = stats_for([pass_event(), pass_event("unknown")])
    r = values(stats, 45)
    assert r["passes_attempted"]["value"] == 2
    assert r["passes_attempted"]["per90"] == 4
    assert r["passes_completed"]["value"] is None
    assert r["pass_completion_pct"]["value"] is None
    assert r["passes_completed"]["observed_numerator"] == 1
    assert r["passes_completed"]["coverage"] == 0.5


def test_incomplete_pass_is_not_progressive_or_a_completed_entry():
    stats, _ = stats_for([pass_event("incomplete")])
    r = values(stats, 90)
    assert r["progressive_passes"]["value"] == 0
    assert r["passes_into_box"]["value"] == 0
    assert r["forward_passes"]["value"] == 1


def test_set_piece_exclusion_and_configurable_progression():
    p = pass_event(pass_type="Free Kick")
    stats, _ = stats_for([p])
    assert values(stats, 90)["progressive_passes"]["value"] == 0
    loose = SETTINGS.metrics.model_copy(update={"progression_absolute_reduction": 100.0})
    assert not progressive((60, 40), (100, 40), loose)


def test_missing_location_suppresses_only_dependent_metrics():
    p = pass_event().model_copy(update={"start_location": None})
    stats, _ = stats_for([p])
    r = values(stats, 90)
    assert r["passes_completed"]["value"] == 1
    assert r["forward_passes"]["value"] is None
    assert r["progressive_passes"]["value"] is None
    assert r["average_action_x"]["value"] is None


def test_carry_distance_and_box_boundaries():
    c = event(
        "Carry",
        player=101,
        play_pattern="Regular Play",
        start_location=location(99, 18),
        detail=CarryDetail(end_location=location(102, 22)),
    )
    stats, _ = stats_for([c])
    r = values(stats, 30)
    assert r["carry_displacement"]["value"] == pytest.approx(5)
    assert r["carry_displacement"]["per90"] == pytest.approx(15)
    assert r["carries_into_box"]["value"] == 1


def test_aggregate_before_rate_not_average_match_rates():
    one, _ = stats_for([pass_event()])
    two, _ = stats_for([pass_event("incomplete")] * 3)
    combined = aggregate_statistics([one, two])
    r = values(combined, 100)
    assert r["pass_completion_pct"]["value"] == 25
    assert r["passes_attempted"]["per90"] == 3.6
    assert values(one, 10)["passes_attempted"]["per90"] != r["passes_attempted"]["per90"]


def test_zero_denominator_and_zero_opportunities_are_distinct():
    r = values(empty_statistics(), 0)
    assert r["shots"]["value"] == 0 and r["shots"]["per90"] is None
    assert r["pass_completion_pct"]["value"] is None


def test_shot_link_xg_is_unique_and_target_must_be_eligible():
    p = pass_event(assisted_shot_id="shot", shot_assist=True)
    shot = event(
        "Shot",
        seconds=101,
        player=102,
        start_location=location(110),
        detail=ShotDetail(xg=0.4, outcome="Goal", shot_type="Open Play"),
    )
    shot = shot.model_copy(update={"event_id": "shot"})
    stats, issues = stats_for([p], {"shot": shot}, {"shot"})
    assert values(stats, 90)["shot_linked_xg_assisted"]["value"] == 0.4
    assert not issues
    bad, issues = stats_for([p], {"shot": shot}, set())
    assert values(bad, 90)["shot_assists"]["value"] is None and issues
    duplicate, issues = stats_for([p, p], {"shot": shot}, {"shot"})
    assert duplicate["shot_assists"].numerator == 1 and issues


@pytest.mark.parametrize(
    "outcome,sot",
    [
        ("Goal", 1),
        ("Saved", 1),
        ("Saved To Post", 1),
        ("Saved to Post", 1),
        ("Saved Off Target", 0),
        ("Post", 0),
        ("Blocked", 0),
    ],
)
def test_shots_on_target_explicit_definition(outcome, sot):
    shot = event(
        "Shot",
        player=101,
        start_location=location(110),
        detail=ShotDetail(xg=0.2, outcome=outcome, shot_type="Penalty"),
    )
    stats, _ = stats_for([shot])
    r = values(stats, 90)
    assert r["shots_on_target"]["value"] == sot
    assert r["nonpenalty_xg"]["value"] == 0
    assert r["penalty_shots"]["value"] == 1


def test_missing_xg_does_not_erase_observed_shot_count():
    shot = event("Shot", player=101, detail=ShotDetail(outcome="Goal", shot_type="Open Play"))
    stats, _ = stats_for([shot])
    r = values(stats, 90)
    assert r["shots"]["value"] == 1
    assert r["xg"]["value"] is None
    assert r["goals"]["value"] == 1


def test_full_feature_pipeline_is_deterministic_and_uses_validated_exposure(tmp_path):
    settings, path = ingested(tmp_path)
    validation = validate_cohort(settings, tmp_path, path)
    manifest = tmp_path / validation["validation_manifest_path"]
    first = build_features(settings, tmp_path, manifest)
    second = build_features(settings, tmp_path, manifest)
    assert first == second
    assert first["player_match_rows"] == first["player_team_season_rows"] == 22
    assert first["event_disposition"] == {"administrative": 10}
    assert first["quarantined_appearances"] == 0
    verified = verify_features(settings, tmp_path, tmp_path / first["feature_manifest_path"])
    assert verified["feature_integrity"] == "VERIFIED"


def test_feature_pipeline_refuses_corrupt_minutes_input(tmp_path):
    settings, path = ingested(tmp_path)
    validation = validate_cohort(settings, tmp_path, path)
    manifest = tmp_path / validation["validation_manifest_path"]
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(IngestionError, match="checksum"):
        build_features(settings, tmp_path, manifest)


def test_quarantined_appearances_contribute_no_rows_or_denominators(tmp_path):
    payloads = complete_payloads()
    events = json.loads(payloads["data/events/101.json"])
    for e in events:
        if e["type"]["name"] == "Half End":
            e["half_end"] = {"early_video_end": True}
    payloads["data/events/101.json"] = json_bytes(events)
    settings = configured(payloads)
    ingestion = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, []))
    assert ingestion["status"] == "COMPLETE", ingestion
    validation = validate_cohort(settings, tmp_path, tmp_path / ingestion["manifest_path"])
    result = build_features(settings, tmp_path, tmp_path / validation["validation_manifest_path"])
    assert result["player_match_rows"] == result["player_team_season_rows"] == 0
    assert result["quarantined_appearances"] == 22


def test_transferred_player_has_separate_team_season_rows(tmp_path):
    payloads = complete_payloads()
    matches = json.loads(payloads["data/matches/37/281.json"])
    matches.append(matches[0] | {"match_id": 102})
    payloads["data/matches/37/281.json"] = json_bytes(matches)
    events = json.loads(payloads["data/events/101.json"])
    lineups = json.loads(payloads["data/lineups/101.json"])
    swap = {101: 201, 201: 101}
    for e in events:
        e["id"] += "-second-match"
        for player in e.get("tactics", {}).get("lineup", []):
            player["player"]["id"] = swap.get(player["player"]["id"], player["player"]["id"])
    for team in lineups:
        for player in team["lineup"]:
            player["player_id"] = swap.get(player["player_id"], player["player_id"])
    payloads["data/events/102.json"] = json_bytes(events)
    payloads["data/lineups/102.json"] = json_bytes(lineups)
    settings = configured(payloads)
    settings = settings.model_copy(
        update={"dataset": settings.dataset.model_copy(update={"expected_match_count": 2})}
    )
    ingestion = ingest_cohort(settings, tmp_path, fetcher=fake_fetcher(payloads, []))
    assert ingestion["status"] == "COMPLETE", ingestion
    validation = validate_cohort(settings, tmp_path, tmp_path / ingestion["manifest_path"])
    result = build_features(settings, tmp_path, tmp_path / validation["validation_manifest_path"])
    assert result["player_match_rows"] == 44
    assert result["player_team_season_rows"] == 24
    assert result["unique_players"] == 22
    verified = verify_features(settings, tmp_path, tmp_path / result["feature_manifest_path"])
    assert verified["feature_integrity"] == "VERIFIED"


def test_feature_verifier_rejects_invented_rate_even_after_rehash(tmp_path):
    settings, path = ingested(tmp_path)
    validation = validate_cohort(settings, tmp_path, path)
    result = build_features(settings, tmp_path, tmp_path / validation["validation_manifest_path"])
    manifest_path = tmp_path / result["feature_manifest_path"]
    report = json.loads(manifest_path.read_bytes())
    artifact = report["artifacts"][0]
    table = manifest_path.parent.parent / artifact["path"]
    rows = [json.loads(line) for line in table.read_bytes().splitlines()]
    rows[0]["values"]["passes_attempted"]["per90"] = 99
    data = b"".join(json_bytes(row) for row in rows)
    table.write_bytes(data)
    artifact.update(sha256=digest(data), byte_count=len(data))
    content = json_bytes(report)
    changed = manifest_path.with_name(digest(content) + ".json")
    changed.write_bytes(content)
    with pytest.raises(IngestionError, match="values/rates"):
        verify_features(settings, tmp_path, changed)


def test_long_pass_uses_yards_field_not_coordinate_displacement():
    p = pass_event(start=99, end=100)
    p = p.model_copy(update={"detail": p.detail.model_copy(update={"length_provider_units": 30.0})})
    stats, _ = stats_for([p])
    assert values(stats, 90)["long_passes"]["value"] == 1
    shorter = p.model_copy(
        update={"detail": p.detail.model_copy(update={"length_provider_units": 29.99})}
    )
    stats, _ = stats_for([shorter])
    assert values(stats, 90)["long_passes"]["value"] == 0
