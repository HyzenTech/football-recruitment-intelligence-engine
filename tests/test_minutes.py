"""Exact synthetic football calculations; no redistributed provider fixtures."""

from datetime import date

import pytest
from test_ingestion import ROOT

from football_recruitment.config import load_settings
from football_recruitment.domain.ids import make_id
from football_recruitment.domain.models import (
    Event,
    EventCard,
    LineupEntry,
    Match,
    PeriodPoint,
    Player,
    PositionObservation,
    QualityStatus,
    TacticalPlayer,
    Team,
    TeamLineup,
)
from football_recruitment.preprocessing.minutes import reconcile_match

MID = make_id("synthetic", "match", 1)
SETTINGS = load_settings(ROOT / "config")


def pid(n):
    return make_id("synthetic", "player", n)


def tid(n):
    return make_id("synthetic", "team", n)


def point(period, seconds):
    return PeriodPoint(period=period, elapsed_seconds=float(seconds))


def position(start=None, end=None, **extra):
    return PositionObservation(
        source_position_id=14,
        source_position_name="Center Midfield",
        start=start or point(1, 0),
        end=end,
        start_reason="Starting XI",
        end_reason="Final Whistle",
        **extra,
    )


def event(kind, period=1, seconds=0, team=1, player=None, **extra):
    return Event(
        match_id=MID,
        event_id="assigned-later",
        index=1,
        period=period,
        elapsed_seconds=float(seconds),
        display_minute=0,
        display_second=0,
        event_type=kind,
        source_type_id=1,
        snapshot_id="synthetic",
        team_id=tid(team),
        player_id=pid(player) if player else None,
        **extra,
    )


def fixture():
    match = Match(
        match_id=MID,
        competition_id=make_id("synthetic", "competition", 1),
        season_id=make_id("synthetic", "season", 1),
        match_date=date(2024, 1, 1),
        home_team_id=tid(1),
        away_team_id=tid(2),
        data_version="synthetic",
        snapshot_id="synthetic",
    )
    teams = []
    es = []
    for team in (1, 2):
        entries = tuple(
            LineupEntry(
                player=Player(player_id=pid(team * 100 + n), player_name=f"Player {team}-{n}"),
                positions=(position(),) if n <= 11 else (),
            )
            for n in range(1, 13)
        )
        teams.append(
            TeamLineup(
                match_id=MID,
                team=Team(team_id=tid(team), team_name=f"Team {team}"),
                entries=entries,
                snapshot_id="synthetic",
            )
        )
        es.append(
            event(
                "Starting XI",
                team=team,
                tactical_lineup=tuple(
                    TacticalPlayer(
                        player_id=entry.player.player_id,
                        source_position_id=14,
                        position_name="Center Midfield",
                    )
                    for entry in entries[:11]
                ),
            )
        )
        for period, seconds in ((1, 3000), (2, 3300)):
            es.extend(
                [
                    event("Half Start", period, team=team),
                    event("Half End", period, seconds, team=team),
                ]
            )
    return match, es, teams


def set_positions(teams, player, observations):
    for i, team in enumerate(teams):
        teams[i] = team.model_copy(
            update={
                "entries": tuple(
                    p.model_copy(update={"positions": tuple(observations)})
                    if p.player.player_id == pid(player)
                    else p
                    for p in team.entries
                )
            }
        )


def reconcile(es, teams, match=None):
    es = sorted(es, key=lambda e: (e.period, e.elapsed_seconds, e.event_type != "Starting XI"))
    es = [
        e.model_copy(update={"index": i, "event_id": f"synthetic-event-{i}"})
        for i, e in enumerate(es, 1)
    ]
    return reconcile_match(
        match or fixture()[0],
        es,
        teams,
        SETTINGS.cohorts.position_groups,
        SETTINGS.cohorts.role_mapping_version,
    )


def appearance(result, player):
    return next(a for a in result.appearances if a.player_id == pid(player))


def test_full_match_added_time_and_halftime_exclusion():
    match, es, teams = fixture()
    result = reconcile(es, teams, match)
    assert len(result.appearances) == 22
    assert len(result.unused_roster) == 2
    assert result.issues == []
    assert appearance(result, 101).playing_seconds == 6300
    assert appearance(result, 101).nominal_minutes == 90
    assert len(result.presence) == 44
    assert (
        sum((x.end.elapsed_seconds - x.start.elapsed_seconds) for x in result.positions)
        == 22 * 6300
    )


def test_substitution_preserves_exact_clock_and_does_not_default_to_ninety():
    _, es, teams = fixture()
    es.append(event("Substitution", 2, 1800.375, player=101, replacement_player_id=pid(112)))
    set_positions(teams, 101, [position(end=point(2, 1800))])
    set_positions(teams, 112, [position(start=point(2, 1800))])
    r = reconcile(es, teams)
    assert appearance(r, 101).playing_seconds == 4800.375
    assert appearance(r, 112).playing_seconds == 1499.625
    assert appearance(r, 112).starter is False
    assert appearance(r, 112).nominal_minutes == pytest.approx(899.625 / 60)


def test_halftime_substitution_has_no_halftime_duration():
    _, es, teams = fixture()
    es.append(event("Substitution", 2, 0, player=101, replacement_player_id=pid(112)))
    set_positions(teams, 101, [position(end=point(1, 3000))])
    set_positions(teams, 112, [position(start=point(2, 0))])
    r = reconcile(es, teams)
    assert appearance(r, 101).playing_seconds == 3000
    assert appearance(r, 112).playing_seconds == 3300


def test_temporary_exit_and_return_subtract_exact_absence():
    _, es, teams = fixture()
    es += [
        event("Player Off", 1, 60.125, player=101, player_off_permanent=False),
        event("Player On", 1, 90.875, player=101),
    ]
    set_positions(teams, 101, [position(end=point(1, 60)), position(start=point(1, 90))])
    r = reconcile(es, teams)
    assert appearance(r, 101).playing_seconds == 6269.25
    assert appearance(r, 101).nominal_minutes == pytest.approx((5400 - 30.75) / 60)


@pytest.mark.parametrize("kind", ["Red Card", "Second Yellow"])
def test_dismissal_ends_presence(kind):
    _, es, teams = fixture()
    es.append(
        event(
            "Foul Committed",
            2,
            1234.567,
            player=101,
            card=EventCard(source_card_id=5, card_type=kind),
        )
    )
    set_positions(teams, 101, [position(end=point(2, 1234))])
    r = reconcile(es, teams)
    assert appearance(r, 101).quality_status == QualityStatus.VALIDATED
    assert appearance(r, 101).playing_seconds == 4234.567


def test_permanent_exit_no_return_and_substitution_while_temporarily_off():
    _, es, teams = fixture()
    es += [
        event("Player Off", 1, 60, player=101, player_off_permanent=True),
        event("Player Off", 1, 100, player=102, player_off_permanent=False),
        event("Substitution", 1, 120, player=102, replacement_player_id=pid(112)),
    ]
    set_positions(teams, 101, [position(end=point(1, 60))])
    set_positions(teams, 102, [position(end=point(1, 100))])
    set_positions(teams, 112, [position(start=point(1, 120))])
    r = reconcile(es, teams)
    assert appearance(r, 101).playing_seconds == 60
    assert appearance(r, 102).playing_seconds == 100
    assert appearance(r, 112).playing_seconds == 6180


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing_end", "UNRELIABLE_PERIOD_BOUNDARY"),
        ("incomplete_video", "UNRELIABLE_PERIOD_BOUNDARY"),
        ("different_end", "UNRELIABLE_PERIOD_BOUNDARY"),
        ("duplicate_xi", "MISSING_OR_DUPLICATE_STARTING_XI"),
        ("ten_starters", "STARTING_XI_NOT_ELEVEN_UNIQUE"),
        ("action_after_end", "EVENT_AFTER_PERIOD_END"),
    ],
)
def test_unreliable_match_quarantines_all_minutes(mutation, code):
    _, es, teams = fixture()
    if mutation == "missing_end":
        es = [e for e in es if not (e.event_type == "Half End" and e.team_id == tid(1))]
    elif mutation == "incomplete_video":
        es[1] = es[1].model_copy(update={"period_boundary_flags": ("late_video_start",)})
    elif mutation == "different_end":
        es[2] = es[2].model_copy(update={"elapsed_seconds": 2999.0})
    elif mutation == "duplicate_xi":
        es.append(es[0])
    elif mutation == "ten_starters":
        es[0] = es[0].model_copy(update={"tactical_lineup": es[0].tactical_lineup[:10]})
    else:
        es.append(event("Pressure", 1, 3000.5, player=101))
    r = reconcile(es, teams)
    assert code in {i["code"] for i in r.issues}
    assert all(a.playing_seconds is None for a in r.appearances)
    assert r.presence == r.positions == []
    assert len(r.appearances) + len(r.unused_roster) == 24


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("overlap", "OVERLAPPING_SOURCE_POSITIONS"),
        ("gap", "POSITION_PRESENCE_DISAGREEMENT"),
        ("reverse", "INVALID_SOURCE_POSITION"),
        ("outside", "POSITION_BOUNDARY_OUTSIDE_PERIOD"),
        ("unknown_on", "PLAYER_ON_WITHOUT_TEMPORARY_EXIT"),
        ("inactive_action", "ACTION_OUTSIDE_RECONSTRUCTED_PRESENCE"),
    ],
)
def test_conflict_is_local_and_never_summed(mutation, code):
    _, es, teams = fixture()
    if mutation == "overlap":
        set_positions(teams, 101, [position(end=point(1, 100)), position(start=point(1, 90))])
    elif mutation == "gap":
        set_positions(teams, 101, [position(end=point(1, 100)), position(start=point(1, 110))])
    elif mutation == "reverse":
        set_positions(
            teams,
            101,
            [
                position(
                    start=point(2, 100),
                    end=point(1, 100),
                    quality_flags=("REVERSED_SOURCE_POSITION_INTERVAL",),
                )
            ],
        )
    elif mutation == "outside":
        set_positions(teams, 101, [position(end=point(2, 3400))])
    elif mutation == "unknown_on":
        es.append(event("Player On", 1, 100, player=101))
    else:
        es += [
            event("Player Off", 1, 100, player=101, player_off_permanent=True),
            event("Pressure", 1, 110, player=101),
        ]
        set_positions(teams, 101, [position(end=point(1, 100))])
    r = reconcile(es, teams)
    assert code in appearance(r, 101).quality_flags
    assert appearance(r, 101).playing_seconds is None
    assert appearance(r, 102).quality_status == QualityStatus.VALIDATED
    assert not any(x.player_id == pid(101) for x in r.presence + r.positions)


def test_zero_length_observation_does_not_add_minutes():
    _, es, teams = fixture()
    set_positions(
        teams,
        101,
        [
            position(),
            position(
                start=point(1, 0),
                end=point(1, 0),
                quality_flags=("ZERO_DURATION_POSITION_OBSERVATION",),
            ),
        ],
    )
    r = reconcile(es, teams)
    assert appearance(r, 101).playing_seconds == 6300
    assert len([x for x in r.positions if x.player_id == pid(101)]) == 2


def test_tactical_shift_aligned_only_to_team_evidence():
    _, es, teams = fixture()
    es.append(event("Tactical Shift", 1, 600.125))
    set_positions(teams, 101, [position(end=point(1, 600)), position(start=point(1, 600))])
    r = reconcile(es, teams)
    spans = [x for x in r.positions if x.player_id == pid(101) and x.start.period == 1]
    assert spans[0].end.elapsed_seconds == spans[1].start.elapsed_seconds == 600.125


def test_invalid_substitution_cannot_introduce_an_already_used_player():
    _, es, teams = fixture()
    es.append(event("Substitution", 2, 100, player=101, replacement_player_id=pid(102)))
    r = reconcile(es, teams)
    assert appearance(r, 101).playing_seconds is None
    assert appearance(r, 102).playing_seconds is None


def test_extra_time_is_playable_and_shootout_is_excluded():
    _, es, teams = fixture()
    for team in (1, 2):
        for period, duration in ((3, 1000), (4, 1100)):
            es += [
                event("Half Start", period, team=team),
                event("Half End", period, duration, team=team),
            ]
    es.append(event("Pressure", 5, 500, player=101))
    r = reconcile(es, teams)
    assert appearance(r, 101).playing_seconds == 8400
    assert appearance(r, 101).nominal_minutes == 120
    assert all(x.end.period < 5 for x in r.presence)


def test_unknown_event_type_prevents_minutes_certification():
    _, es, teams = fixture()
    es.append(event("Future State Change", 1, 500, quality_flags=("UNREVIEWED_EVENT_TYPE",)))
    r = reconcile(es, teams)
    assert all(a.quality_status == QualityStatus.NEEDS_REVIEW for a in r.appearances)


def test_bench_dismissal_does_not_create_an_appearance():
    _, es, teams = fixture()
    es.append(
        event(
            "Bad Behaviour",
            2,
            100,
            player=112,
            card=EventCard(source_card_id=5, card_type="Red Card"),
        )
    )
    r = reconcile(es, teams)
    assert len(r.appearances) == 22
    assert all(a.quality_status == QualityStatus.VALIDATED for a in r.appearances)
    assert "BENCH_OR_POST_EXIT_DISMISSAL" in {i["code"] for i in r.issues}
