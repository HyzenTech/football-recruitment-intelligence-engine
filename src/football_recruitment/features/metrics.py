"""Sufficient statistics aggregate before rates; unavailable evidence never becomes zero."""

from math import hypot

from pydantic import Field

from football_recruitment.domain.models import Contract, NonNegative

FEATURE_VERSION = "features-0.4.0"
COUNTS = (
    "passes_attempted passes_completed forward_passes progressive_passes "
    "passes_into_final_third passes_into_box switches crosses long_passes "
    "carries progressive_carries carries_into_final_third carries_into_box "
    "shot_assists shots shots_on_target goals shots_inside_box penalty_shots nonpenalty_shots "
    "pressures counterpressures interceptions recovery_attempts recoveries "
    "tackles blocks clearances "
    "miscontrols dispossessions event_involvements final_third_actions box_actions"
).split()
SUMS = ["carry_displacement", "xg", "nonpenalty_xg", "shot_linked_xg_assisted"]
MEANS = ["average_shot_distance", "average_action_x", "average_action_y"]
PERCENTAGES = ["pass_completion_pct"]
METRICS = tuple(COUNTS + SUMS + MEANS + PERCENTAGES)
ADMIN = {
    "Starting XI",
    "Half Start",
    "Half End",
    "Tactical Shift",
    "Substitution",
    "Player On",
    "Player Off",
    "Bad Behaviour",
    "Injury Stoppage",
    "Referee Ball-Drop",
}
SHOT_OUTCOMES = {
    "Goal",
    "Saved",
    "Saved To Post",
    "Saved to Post",
    "Saved Off Target",
    "Off T",
    "Post",
    "Blocked",
    "Wayward",
}


class Statistic(Contract):
    numerator: NonNegative = 0.0
    samples: int = Field(default=0, ge=0, strict=True)
    missing: int = Field(default=0, ge=0, strict=True)


def empty_statistics():
    return {name: Statistic() for name in METRICS}


def add(stats, name, value):
    old = stats[name]
    stats[name] = Statistic(
        numerator=old.numerator + (float(value) if value is not None else 0.0),
        samples=old.samples + 1,
        missing=old.missing + (value is None),
    )


def aggregate_statistics(rows):
    result = empty_statistics()
    for row in rows:
        for name in METRICS:
            a, b = result[name], row[name]
            result[name] = Statistic(
                numerator=a.numerator + b.numerator,
                samples=a.samples + b.samples,
                missing=a.missing + b.missing,
            )
    return result


def values(stats, minutes):
    """Strict completeness: any missing opportunity suppresses the metric and its rate."""
    result = {}
    for name, stat in stats.items():
        value = None if stat.missing else stat.numerator
        if name in MEANS + PERCENTAGES:
            value = value / stat.samples if value is not None and stat.samples else None
            if name in PERCENTAGES and value is not None:
                value *= 100.0
        per90 = value * 90 / minutes if value is not None and minutes > 0 else None
        if name in MEANS + PERCENTAGES:
            per90 = None
        result[name] = {
            "value": value,
            "per90": per90,
            "observed_numerator": stat.numerator,
            "samples": stat.samples,
            "missing": stat.missing,
            "coverage": (stat.samples - stat.missing) / stat.samples if stat.samples else None,
        }
    return result


def xy(location, settings):
    return (
        (location.x * settings.provider_pitch_length, location.y * settings.provider_pitch_width)
        if location
        else None
    )


def inside_box(point, settings):
    return point[0] >= settings.penalty_area_start_x and (
        settings.penalty_area_y_min <= point[1] <= settings.penalty_area_y_max
    )


def progressive(start, end, settings):
    if start is None or end is None:
        return None
    distance = hypot(
        settings.provider_pitch_length - start[0], settings.provider_pitch_width / 2 - start[1]
    )
    reduction = distance - hypot(
        settings.provider_pitch_length - end[0], settings.provider_pitch_width / 2 - end[1]
    )
    return (
        distance > 0
        and (not settings.progression_requires_forward or end[0] > start[0])
        and reduction
        >= max(
            settings.progression_absolute_reduction,
            settings.progression_relative_reduction * distance,
        )
    )


def accumulate_event(stats, event, settings, event_lookup, eligible_shots, used_shots, issues):
    """Consumes only canonical events admitted by the appearance/presence gate."""
    kind = event.event_type
    if kind in ADMIN:
        return
    add(stats, "event_involvements", 1)
    start = xy(event.start_location, settings)
    # Spatial summaries refer to located actions, not administrative or unlocated events.
    if start:
        add(stats, "average_action_x", start[0])
        add(stats, "average_action_y", start[1])
        add(stats, "final_third_actions", start[0] >= settings.final_third_start_x)
        add(stats, "box_actions", inside_box(start, settings))
    detail = event.detail
    if kind in {"Pass", "Carry"}:
        is_pass = kind == "Pass"
        add(stats, "passes_attempted" if is_pass else "carries", 1)
        end = xy(detail.end_location, settings)
        completed = (
            None
            if is_pass and detail.outcome == "unknown"
            else (detail.outcome == "complete" if is_pass else True)
        )
        if is_pass:
            add(stats, "passes_completed", completed)
            add(stats, "pass_completion_pct", completed)
            add(stats, "forward_passes", end[0] > start[0] if start and end else None)
            add(stats, "switches", detail.switch)
            add(stats, "crosses", detail.cross)
            add(
                stats,
                "long_passes",
                detail.length_provider_units >= settings.long_pass_minimum_yards
                if detail.length_provider_units is not None
                else None,
            )
        else:
            add(
                stats,
                "carry_displacement",
                hypot(end[0] - start[0], end[1] - start[1]) if start and end else None,
            )
        prefix = "passes" if is_pass else "carries"
        for name, condition in (
            (
                f"{prefix}_into_final_third",
                start and end and start[0] < settings.final_third_start_x <= end[0],
            ),
            (
                f"{prefix}_into_box",
                start and end and not inside_box(start, settings) and inside_box(end, settings),
            ),
        ):
            add(
                stats,
                name,
                False
                if completed is False
                else (bool(condition) if completed is True and start and end else None),
            )
        qualifies = (
            completed if (is_pass and settings.pass_progression_requires_completion) else True
        )
        if settings.progression_open_play_only:
            open_play = (
                None
                if event.play_pattern is None
                else event.play_pattern in settings.open_play_patterns
            )
            # Explicit pass restart types remain excluded even with an open-play pattern.
            if is_pass and detail.pass_type in {
                "Corner",
                "Free Kick",
                "Goal Kick",
                "Kick Off",
                "Throw-in",
            }:
                open_play = False
        else:
            open_play = True
        add(
            stats,
            "progressive_passes" if is_pass else "progressive_carries",
            False
            if qualifies is False or open_play is False
            else (
                progressive(start, end, settings)
                if qualifies is True and open_play is True
                else None
            ),
        )
        if is_pass and (detail.assisted_shot_id or detail.shot_assist or detail.goal_assist):
            shot = event_lookup.get(detail.assisted_shot_id)
            valid = (
                shot is not None
                and shot.event_type == "Shot"
                and shot.team_id == event.team_id
                and shot.event_id in eligible_shots
                and shot.period == event.period
                and shot.elapsed_seconds >= event.elapsed_seconds
                and shot.detail.key_pass_id in (None, event.event_id)
                and shot.event_id not in used_shots
            )
            if valid:
                used_shots.add(shot.event_id)
                add(stats, "shot_assists", 1)
                add(stats, "shot_linked_xg_assisted", shot.detail.xg)
            else:
                add(stats, "shot_assists", None)
                add(stats, "shot_linked_xg_assisted", None)
                issues.append(
                    {"code": "INVALID_OR_INELIGIBLE_SHOT_LINK", "event_id": event.event_id}
                )
    elif kind == "Shot":
        add(stats, "shots", 1)
        known = detail.outcome in SHOT_OUTCOMES
        if not known:
            issues.append({"code": "UNKNOWN_SHOT_OUTCOME", "event_id": event.event_id})
        add(stats, "goals", detail.outcome == "Goal" if known else None)
        add(
            stats,
            "shots_on_target",
            detail.outcome in {"Goal", "Saved", "Saved To Post", "Saved to Post"}
            if known
            else None,
        )
        add(stats, "xg", detail.xg)
        penalty = None if detail.shot_type is None else detail.shot_type == "Penalty"
        add(stats, "penalty_shots", penalty)
        add(stats, "nonpenalty_shots", not penalty if penalty is not None else None)
        add(stats, "nonpenalty_xg", 0 if penalty else (detail.xg if penalty is False else None))
        add(
            stats,
            "average_shot_distance",
            hypot(
                settings.provider_pitch_length - start[0],
                settings.provider_pitch_width / 2 - start[1],
            )
            if start
            else None,
        )
        add(stats, "shots_inside_box", inside_box(start, settings) if start else None)
    else:
        direct = {
            "Pressure": "pressures",
            "Interception": "interceptions",
            "Ball Recovery": "recovery_attempts",
            "Block": "blocks",
            "Clearance": "clearances",
            "Miscontrol": "miscontrols",
            "Dispossessed": "dispossessions",
        }
        if kind in direct:
            add(stats, direct[kind], 1)
        if kind == "Pressure":
            add(stats, "counterpressures", event.counterpress)
        elif kind == "Ball Recovery":
            add(
                stats,
                "recoveries",
                not detail.recovery_failure
                if detail and detail.recovery_failure is not None
                else None,
            )
        elif kind == "Duel":
            add(stats, "tackles", detail.subtype == "Tackle" if detail and detail.subtype else None)
