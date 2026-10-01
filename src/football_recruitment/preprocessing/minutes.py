"""Event-driven presence, independently checked against source position observations.

Intervals are half-open. Normal actions at an exit timestamp are accepted at that
boundary because provider ordering does not establish sub-second physical presence.
Source position clocks have second precision: only a nearby evidenced boundary
within one second may be aligned. No reversed observation is repaired.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from football_recruitment.domain.models import (
    Appearance,
    Event,
    Match,
    MatchPeriod,
    PeriodPoint,
    PositionInterval,
    PresenceInterval,
    QualityStatus,
    TeamLineup,
)
from football_recruitment.ingestion.pipeline import check_match_records

MINUTES_VERSION = "presence-0.3.0"
CLOCK_TOLERANCE = 1.0
EPSILON = 0.000001
NOMINAL_SECONDS = {1: 2700.0, 2: 2700.0, 3: 900.0, 4: 900.0}
NOMINAL_BASE = {1: 0.0, 2: 2700.0, 3: 5400.0, 4: 6300.0}
DISMISSAL_CARDS = {"Red Card", "Second Yellow"}
ADMIN_TYPES = {
    "Starting XI",
    "Half Start",
    "Half End",
    "Substitution",
    "Player Off",
    "Player On",
    "Bad Behaviour",
    "Tactical Shift",
    "Injury Stoppage",
}


@dataclass
class Reconciliation:
    periods: list[MatchPeriod] = field(default_factory=list)
    appearances: list[Appearance] = field(default_factory=list)
    presence: list[PresenceInterval] = field(default_factory=list)
    positions: list[PositionInterval] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    unused_roster: list[dict] = field(default_factory=list)


def reconcile_match(
    match: Match,
    events: list[Event],
    lineups: list[TeamLineup],
    position_groups: dict,
    role_mapping_version: str,
) -> Reconciliation:
    """Never turn a roster-only row or contradictory state into validated minutes."""
    result = Reconciliation()
    fatal = []
    flags = defaultdict(set)

    def issue(code, *, team=None, player=None, event=None, severity="error", **details):
        result.issues.append(
            {
                "code": code,
                "severity": severity,
                "team_id": team,
                "player_id": player,
                "event_id": event,
                **details,
            }
        )
        if severity == "error":
            if player:
                flags[player].add(code)
            else:
                fatal.append(code)

    try:
        check_match_records(match, events, lineups)
    except ValueError as error:
        issue("CANONICAL_IDENTITY_FAILURE", detail=str(error))
        return result
    if any(e.match_id != match.match_id for e in events) or any(
        t.match_id != match.match_id for t in lineups
    ):
        issue("FOREIGN_MATCH_RECORD")
        return result
    teams = {t.team.team_id for t in lineups}
    roster = {p.player.player_id: (t.team.team_id, p) for t in lineups for p in t.entries}
    if len(roster) != sum(len(t.entries) for t in lineups):
        issue("CROSS_TEAM_PLAYER_ID_COLLISION")
        return result
    if any("UNREVIEWED_EVENT_TYPE" in e.quality_flags for e in events):
        issue("UNREVIEWED_EVENT_TYPE")
    playable = sorted({e.period for e in events if e.period < 5})
    # General support includes extra time; only complete consecutive periods are usable.
    if playable not in ([1, 2], [1, 2, 3, 4]):
        issue("INCOMPLETE_PLAYABLE_PERIODS")
    durations = {}
    for period in playable:
        start = [e for e in events if e.period == period and e.event_type == "Half Start"]
        end = [e for e in events if e.period == period and e.event_type == "Half End"]
        valid = (
            len(start) == len(end) == 2
            and {e.team_id for e in start} == teams
            and {e.team_id for e in end} == teams
            and all(e.elapsed_seconds == 0 and not e.period_boundary_flags for e in start)
            and len({e.elapsed_seconds for e in end}) == 1
            and all(not e.period_boundary_flags for e in end)
            and end[0].elapsed_seconds > 0
        )
        if not valid:
            issue("UNRELIABLE_PERIOD_BOUNDARY", period=period)
            continue
        durations[period] = end[0].elapsed_seconds
        if any(
            e.elapsed_seconds > durations[period] + EPSILON for e in events if e.period == period
        ):
            issue("EVENT_AFTER_PERIOD_END", period=period)
        result.periods.append(
            MatchPeriod(
                match_id=match.match_id,
                period=period,
                duration_seconds=durations[period],
                nominal_base_seconds=NOMINAL_BASE[period],
                quality_status=QualityStatus.VALIDATED,
            )
        )
    starters = {}
    start_positions = {}
    for team in sorted(teams):
        xis = [e for e in events if e.event_type == "Starting XI" and e.team_id == team]
        if len(xis) != 1 or xis[0].period != 1 or xis[0].elapsed_seconds != 0:
            issue("MISSING_OR_DUPLICATE_STARTING_XI", team=team)
            continue
        ids = [p.player_id for p in xis[0].tactical_lineup]
        if len(ids) != 11 or len(set(ids)) != 11:
            issue("STARTING_XI_NOT_ELEVEN_UNIQUE", team=team)
            continue
        starters[team] = set(ids)
        start_positions.update({p.player_id: p.position_name for p in xis[0].tactical_lineup})
    if fatal:
        # Football boundaries are unavailable: no estimated intervals are emitted.
        for player, (team, entry) in sorted(roster.items()):
            if entry.positions or player in start_positions:
                result.appearances.append(
                    Appearance(
                        match_id=match.match_id,
                        team_id=team,
                        player_id=player,
                        starter=player in start_positions,
                        starting_position=start_positions.get(player),
                        quality_status=QualityStatus.NEEDS_REVIEW,
                        quality_flags=tuple(sorted(set(fatal))),
                    )
                )
            else:
                result.unused_roster.append(
                    {
                        "team_id": team,
                        "player_id": player,
                        "quality_status": "EXCLUDED",
                        "reason": "roster_only_no_playing_evidence",
                    }
                )
        result.periods = []
        return result

    active = {p for ps in starters.values() for p in ps}
    temporary = set()
    retired = set()
    introduced = set(active)
    raw_presence = defaultdict(list)
    anchors = defaultdict(list)
    evidence = defaultdict(list)
    for event in events:
        if event.period < 5 and (event.event_type in ADMIN_TYPES or event.card):
            if event.event_type in {"Tactical Shift", "Starting XI"}:
                for player, (team, _) in roster.items():
                    if team == event.team_id:
                        anchors[player, event.period].append(event.elapsed_seconds)
            elif event.event_type in {"Substitution", "Player Off", "Player On"} or event.card:
                for player in (event.player_id, event.replacement_player_id):
                    if player:
                        anchors[player, event.period].append(event.elapsed_seconds)
    for period, duration in durations.items():
        for player in roster:
            anchors[player, period].extend([0.0, duration])
        opened = {p: (0.0, "period_start", ()) for p in active}

        def close(player, clock, reason, event, opened=opened, period=period):
            if player in opened:
                start, start_reason, ids = opened.pop(player)
                if clock > start:
                    raw_presence[player].append(
                        (period, start, clock, start_reason, reason, (*ids, event.event_id))
                    )

        transitions = sorted(
            (e for e in events if e.period == period), key=lambda e: (e.elapsed_seconds, e.index)
        )
        for event in transitions:
            p = event.player_id
            t = event.elapsed_seconds
            if event.event_type == "Substitution":
                incoming = event.replacement_player_id
                if not incoming or p not in active | temporary or incoming in introduced:
                    issue("INVALID_SUBSTITUTION_STATE", player=p, event=event.event_id)
                    if incoming:
                        flags[incoming].add("INVALID_SUBSTITUTION_STATE")
                    continue
                close(p, t, "substitution", event)
                active.discard(p)
                temporary.discard(p)
                retired.add(p)
                active.add(incoming)
                introduced.add(incoming)
                opened[incoming] = (t, "substitution", (event.event_id,))
                start_positions[incoming] = next(
                    (
                        x.source_position_name
                        for x in roster[incoming][1].positions
                        if x.start
                        and x.start.period == period
                        and abs(x.start.elapsed_seconds - t) <= CLOCK_TOLERANCE
                    ),
                    None,
                )
            elif event.event_type == "Player Off":
                if p not in active:
                    issue("PLAYER_OFF_NOT_ACTIVE", player=p, event=event.event_id)
                    continue
                close(
                    p,
                    t,
                    "permanent_exit" if event.player_off_permanent else "temporary_exit",
                    event,
                )
                active.remove(p)
                (retired if event.player_off_permanent else temporary).add(p)
            elif event.event_type == "Player On":
                if p not in temporary or p in retired:
                    issue("PLAYER_ON_WITHOUT_TEMPORARY_EXIT", player=p, event=event.event_id)
                    continue
                temporary.remove(p)
                active.add(p)
                opened[p] = (t, "return", (event.event_id,))
            elif event.card and event.card.card_type in DISMISSAL_CARDS:
                if p in active | temporary:
                    close(p, t, "dismissal", event)
                    active.discard(p)
                    temporary.discard(p)
                    retired.add(p)
                else:
                    issue(
                        "BENCH_OR_POST_EXIT_DISMISSAL",
                        player=p,
                        event=event.event_id,
                        severity="warning",
                    )
            if p and event.event_type not in ADMIN_TYPES:
                evidence[p].append(event)
        for p, (start, reason, ids) in sorted(opened.items()):
            if duration > start:
                raw_presence[p].append((period, start, duration, reason, "period_end", ids))
        for team in teams:
            if sum(roster[p][0] == team for p in active) > 11:
                issue("TEAM_CAPACITY_EXCEEDED", team=team, period=period)

    def align(point, player):
        values = anchors[player, point.period]
        nearest = min(values, key=lambda x: (abs(x - point.elapsed_seconds), x))
        return (
            nearest
            if abs(nearest - point.elapsed_seconds) <= CLOCK_TOLERANCE
            else point.elapsed_seconds
        )

    mapping = {pid: group for group, ids in position_groups.items() for pid in ids}
    for player, (team, entry) in sorted(roster.items()):
        spans = raw_presence[player]
        if player not in introduced and not entry.positions:
            if evidence[player]:
                issue("EVENT_FOR_UNUSED_ROSTER_PLAYER", player=player)
            result.unused_roster.append(
                {
                    "team_id": team,
                    "player_id": player,
                    "quality_status": "NEEDS_REVIEW" if flags[player] else "EXCLUDED",
                    "reason": "roster_only_no_playing_evidence",
                }
            )
            continue
        if not spans:
            issue("NO_POSITIVE_PLAYING_TIME", player=player)
        source_spans = defaultdict(list)
        for obs in entry.positions:
            if "ZERO_DURATION_POSITION_OBSERVATION" in obs.quality_flags:
                issue("ZERO_DURATION_POSITION_OBSERVATION", player=player, severity="warning")
                continue
            if obs.quality_flags or obs.start is None:
                issue(
                    "INVALID_SOURCE_POSITION", player=player, source_flags=list(obs.quality_flags)
                )
                continue
            end = obs.end or PeriodPoint(
                period=max(durations), elapsed_seconds=durations[max(durations)]
            )
            if obs.start.period not in durations or end.period not in durations:
                issue("POSITION_PERIOD_OUTSIDE_MATCH", player=player)
                continue
            for period in range(obs.start.period, end.period + 1):
                a = align(obs.start, player) if period == obs.start.period else 0.0
                b = align(end, player) if period == end.period else durations[period]
                if not 0 <= a <= b <= durations[period]:
                    issue("POSITION_BOUNDARY_OUTSIDE_PERIOD", player=player, period=period)
                    continue
                if b > a:
                    source_spans[period].append((a, b, obs))
        if not entry.positions:
            issue("APPEARANCE_WITHOUT_POSITION_EVIDENCE", player=player)
        elif player in starters[team]:
            initial = [
                o
                for o in entry.positions
                if o.start == PeriodPoint(period=1, elapsed_seconds=0.0) and o.end != o.start
            ]
            if len(initial) != 1 or initial[0].source_position_name != start_positions[player]:
                issue("STARTING_POSITION_DISAGREEMENT", player=player)
        candidate_positions = []
        for period in durations:
            positions = sorted(source_spans[period], key=lambda x: (x[0], x[1]))
            prev = -1.0
            for a, b, _ in positions:
                if a < prev - EPSILON:
                    issue(
                        "OVERLAPPING_SOURCE_POSITIONS",
                        player=player,
                        period=period,
                        overlap_seconds=prev - a,
                    )
                prev = max(prev, b)
            # Compare presence at every boundary rather than comparing only totals.
            present = [(a, b) for per, a, b, *_ in spans if per == period]
            cuts = sorted(
                {x for a, b in present for x in (a, b)}
                | {x for a, b, _ in positions for x in (a, b)}
            )
            discrepancy = 0.0
            for a, b in zip(cuts, cuts[1:], strict=False):
                middle = (a + b) / 2
                in_event = any(x <= middle < y for x, y in present)
                in_source = any(x <= middle < y for x, y, _ in positions)
                if in_event != in_source:
                    discrepancy += b - a
            if discrepancy > EPSILON:
                issue(
                    "POSITION_PRESENCE_DISAGREEMENT",
                    player=player,
                    period=period,
                    disagreement_seconds=round(discrepancy, 6),
                )
            for a, b, obs in positions:
                for x, y in present:
                    lo, hi = max(a, x), min(b, y)
                    if hi > lo:
                        if obs.source_position_id not in mapping:
                            issue("UNMAPPED_POSITION", player=player)
                            continue
                        candidate_positions.append(
                            PositionInterval(
                                match_id=match.match_id,
                                team_id=team,
                                player_id=player,
                                start=PeriodPoint(period=period, elapsed_seconds=lo),
                                end=PeriodPoint(period=period, elapsed_seconds=hi),
                                start_reason=obs.start_reason,
                                end_reason=obs.end_reason,
                                source_position_id=obs.source_position_id,
                                source_position_name=obs.source_position_name,
                                position_group=mapping[obs.source_position_id],
                                mapping_version=role_mapping_version,
                            )
                        )
        for event in evidence[player]:
            # Cards on the bench legitimately do not prove presence.
            if event.event_type == "Bad Behaviour" or event.period == 5:
                continue
            if not any(
                per == event.period and a - EPSILON <= event.elapsed_seconds <= b + EPSILON
                for per, a, b, *_ in spans
            ):
                issue("ACTION_OUTSIDE_RECONSTRUCTED_PRESENCE", player=player, event=event.event_id)
        seconds = sum(b - a for _, a, b, *_ in spans)
        nominal = (
            sum(
                max(0.0, min(b, NOMINAL_SECONDS[p]) - min(a, NOMINAL_SECONDS[p]))
                for p, a, b, *_ in spans
            )
            / 60.0
        )
        if seconds > sum(durations.values()) + EPSILON:
            issue("IMPOSSIBLE_PLAYING_SECONDS", player=player)
        # Invalid card clocks alone are warnings when event evidence independently resolves them.
        for card in entry.cards:
            matching = [
                e
                for e in events
                if e.player_id == player and e.card and e.card.card_type == card.card_type
            ]
            if not matching:
                issue(
                    "LINEUP_CARD_WITHOUT_EVENT",
                    player=player,
                    severity="error" if card.card_type in DISMISSAL_CARDS else "warning",
                )
            elif card.time is None:
                if len(matching) == 1:
                    issue("CARD_CLOCK_RESOLVED_FROM_EVENT", player=player, severity="warning")
                else:
                    issue("AMBIGUOUS_SOURCE_CARD", player=player)
            elif not any(
                e.period == card.time.period
                and abs(e.elapsed_seconds - card.time.elapsed_seconds) <= CLOCK_TOLERANCE
                for e in matching
            ):
                issue(
                    "CARD_EVENT_CLOCK_DISAGREEMENT",
                    player=player,
                    severity="error" if card.card_type in DISMISSAL_CARDS else "warning",
                )
        quality = QualityStatus.NEEDS_REVIEW if flags[player] or fatal else QualityStatus.VALIDATED
        if quality == QualityStatus.VALIDATED and seconds <= 0:
            quality = QualityStatus.EXCLUDED
        result.appearances.append(
            Appearance(
                match_id=match.match_id,
                team_id=team,
                player_id=player,
                starter=any(player in ids for ids in starters.values()),
                starting_position=start_positions.get(player),
                playing_seconds=seconds if quality == QualityStatus.VALIDATED else None,
                nominal_minutes=nominal if quality == QualityStatus.VALIDATED else None,
                minutes_method="event_state_crosschecked_with_lineup_positions",
                minutes_version=MINUTES_VERSION,
                quality_status=quality,
                quality_flags=tuple(sorted(flags[player] | set(fatal))),
            )
        )
        if quality == QualityStatus.VALIDATED:
            result.presence.extend(
                PresenceInterval(
                    match_id=match.match_id,
                    team_id=team,
                    player_id=player,
                    start=PeriodPoint(period=p, elapsed_seconds=a),
                    end=PeriodPoint(period=p, elapsed_seconds=b),
                    start_reason=sr,
                    end_reason=er,
                    evidence_event_ids=ids,
                    quality_status=quality,
                )
                for p, a, b, sr, er, ids in spans
            )
            result.positions.extend(
                x.model_copy(update={"quality_status": quality}) for x in candidate_positions
            )
    return result
