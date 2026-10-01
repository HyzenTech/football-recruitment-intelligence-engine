"""Synthetic boundary cases; no redistributed provider records."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from football_recruitment.domain.eligibility import AgeConstraint, Eligibility
from football_recruitment.domain.ids import make_id
from football_recruitment.domain.models import (
    Appearance,
    Event,
    LineupEntry,
    Location,
    Match,
    PeriodPoint,
    Player,
    PositionObservation,
    PresenceInterval,
    ProviderSnapshot,
    Team,
    TeamLineup,
)


def player(**changes):
    return Player(player_id="synthetic:player:7", player_name="Synthetic Player", **changes)


def interval(start=(1, 0.0), end=(1, 60.0)):
    return PresenceInterval(
        match_id="synthetic:match:1",
        team_id="synthetic:team:2",
        player_id="synthetic:player:7",
        start=PeriodPoint(period=start[0], elapsed_seconds=start[1]),
        end=PeriodPoint(period=end[0], elapsed_seconds=end[1]),
        start_reason="Starting XI",
        end_reason="Substitution",
    )


def event(**changes):
    data = {
        "match_id": "synthetic:match:1",
        "event_id": "synthetic-event-1",
        "index": 1,
        "period": 1,
        "elapsed_seconds": 0.0,
        "display_minute": 0,
        "display_second": 0,
        "event_type": "Half Start",
        "source_type_id": 18,
        "snapshot_id": "synthetic-snapshot",
    }
    return Event(**(data | changes))


def test_same_provider_integer_is_not_same_identity_across_sources():
    assert make_id("statsbomb", "player", 7) != make_id("football-data", "player", 7)
    assert make_id("statsbomb", "player", 7) != make_id("statsbomb", "team", 7)


@pytest.mark.parametrize("native", [True, "", "7:8", 1.5])
def test_invalid_native_identity_is_not_silently_coerced(native):
    with pytest.raises(ValueError):
        make_id("synthetic", "player", native)


def test_entity_reference_rejects_wrong_kind():
    with pytest.raises(ValidationError, match="player ID"):
        Player(player_id="synthetic:team:7", player_name="Wrong entity")


def test_unknown_age_cannot_satisfy_u23():
    requirement = AgeConstraint(max_age=23, as_of=date(2024, 5, 18))
    assert requirement.evaluate(player()) == Eligibility.UNKNOWN
    assert requirement.evaluate(player()) != Eligibility.ELIGIBLE


@pytest.mark.parametrize(
    "day,result",
    [
        (date(2024, 5, 17), Eligibility.ELIGIBLE),
        (date(2024, 5, 18), Eligibility.INELIGIBLE),
    ],
)
def test_age_boundary_uses_reference_date_and_birthday(day, result):
    subject = player(birth_date=date(2000, 5, 18), birth_date_source="https://example.org/source")
    assert AgeConstraint(max_age=23, as_of=day).evaluate(subject) == result


def test_birth_date_requires_evidence_and_cannot_be_after_reference_date():
    with pytest.raises(ValidationError, match="evidence"):
        player(birth_date=date(2000, 1, 1))
    subject = player(birth_date=date(2025, 1, 1), birth_date_source="https://example.org/source")
    with pytest.raises(ValueError, match="reference date"):
        AgeConstraint(max_age=23, as_of=date(2024, 5, 18)).evaluate(subject)


@pytest.mark.parametrize(
    "start,end", [((1, 60.0), (1, 30.0)), ((2, 0.0), (1, 3000.0)), ((1, 60.0), (1, 60.0))]
)
def test_invalid_or_zero_length_intervals_are_rejected(start, end):
    with pytest.raises(ValidationError, match="end after"):
        interval(start, end)


def test_period_reset_and_stoppage_are_not_negative_time():
    value = interval((1, 2900.0), (2, 10.0))
    assert value.end.period == 2
    # Duration must later use period bounds; subtracting the two second values is wrong.


@pytest.mark.parametrize("seconds", [-1.0, float("nan"), float("inf"), True])
def test_invalid_elapsed_values_fail_before_analytics(seconds):
    with pytest.raises(ValidationError):
        PeriodPoint(period=1, elapsed_seconds=seconds)


def test_unresolved_positions_do_not_pretend_to_be_validated_minutes():
    observation = PositionObservation(
        source_position_id=14,
        source_position_name="Synthetic midfield",
        start=PeriodPoint(period=1, elapsed_seconds=0.0),
        end=None,
        start_reason="Starting XI",
        end_reason="Final Whistle",
    )
    assert observation.end is None
    with pytest.raises(ValidationError, match="positive playing seconds"):
        Appearance(
            match_id="synthetic:match:1",
            team_id="synthetic:team:2",
            player_id="synthetic:player:7",
            starter=True,
            quality_status="VALIDATED",
        )


def test_validated_elapsed_appearance_may_exceed_ninety_minutes():
    value = Appearance(
        match_id="synthetic:match:1",
        team_id="synthetic:team:2",
        player_id="synthetic:player:7",
        starter=True,
        playing_seconds=6000.0,
        nominal_minutes=90.0,
        minutes_method="elapsed_including_stoppage",
        minutes_version="synthetic-1",
        quality_status="VALIDATED",
    )
    assert value.playing_seconds == 6000.0


def test_unused_team_sheet_entry_does_not_imply_appearance():
    entry = LineupEntry(player=player(), positions=())
    assert entry.positions == ()
    with pytest.raises(ValidationError, match="Duplicate player"):
        TeamLineup(
            match_id="synthetic:match:1",
            team=Team(team_id="synthetic:team:2", team_name="Team"),
            entries=(entry, entry),
            snapshot_id="synthetic-snapshot",
        )


def test_administrative_event_preserves_unknown_actor_and_location():
    value = event()
    assert value.player_id is None and value.start_location is None
    assert value.counterpress is None


def test_actor_requires_team_and_matching_event_details():
    with pytest.raises(ValidationError, match="requires a team"):
        event(player_id="synthetic:player:7")
    with pytest.raises(ValidationError, match="matching typed detail"):
        event(event_type="Pass")
    with pytest.raises(ValidationError, match="do not match"):
        event(detail={"kind": "carry"})


@pytest.mark.parametrize("x,y", [(-0.1, 0.5), (1.01, 0.5), (0.5, float("nan"))])
def test_normalized_coordinate_boundary_rejects_impossible_positions(x, y):
    with pytest.raises(ValidationError):
        Location(x=x, y=y)


def test_unknown_canonical_fields_are_schema_changes_not_silently_dropped():
    with pytest.raises(ValidationError, match="Extra inputs"):
        event(unreviewed_provider_flag=True)


def test_snapshot_requires_timezone_and_content_hash():
    data = {
        "snapshot_id": "synthetic",
        "provider": "synthetic",
        "revision": "synthetic-v1",
        "retrieved_at": datetime(2024, 1, 1),
        "source_url": "https://example.org/source",
        "sha256": "a" * 64,
        "license_url": "https://example.org/license",
        "schema_version": "1",
    }
    with pytest.raises(ValidationError, match="timezone"):
        ProviderSnapshot(**data)
    with pytest.raises(ValidationError):
        ProviderSnapshot(**(data | {"retrieved_at": "2024-01-01T00:00:00Z", "sha256": "bad"}))


def test_match_rejects_partial_score_and_same_team():
    data = {
        "match_id": "synthetic:match:1",
        "competition_id": "synthetic:competition:1",
        "season_id": "synthetic:season:1",
        "match_date": date(2024, 1, 1),
        "home_team_id": "synthetic:team:1",
        "away_team_id": "synthetic:team:2",
        "data_version": "synthetic-1",
        "snapshot_id": "synthetic-snapshot",
    }
    with pytest.raises(ValidationError, match="complete or unknown"):
        Match(**(data | {"home_score": 1}))
    with pytest.raises(ValidationError, match="distinct teams"):
        Match(**(data | {"away_team_id": "synthetic:team:1"}))
