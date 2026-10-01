"""Pinned StatsBomb adapter: provider JSON terminates at this canonical boundary."""

import re

from pydantic import ValidationError

from football_recruitment.config import DatasetSettings
from football_recruitment.domain.ids import make_id
from football_recruitment.domain.models import (
    CardObservation,
    CarryDetail,
    Competition,
    CompetitionSeason,
    DefensiveDetail,
    Event,
    EventCard,
    LineupEntry,
    Location,
    Match,
    PassDetail,
    PeriodPoint,
    Player,
    PositionObservation,
    Season,
    ShotDetail,
    ShotEndpoint,
    TacticalPlayer,
    Team,
    TeamLineup,
)
from football_recruitment.ingestion.storage import IngestionError, SnapshotStore
from football_recruitment.providers.base import EventProvider

MAPPING_VERSION = "statsbomb-canonical-0.2.1"
PERIOD_BASE = {1: 0, 2: 2700, 3: 5400, 4: 6300}
EVENT_TYPES = {
    2: "Ball Recovery",
    3: "Dispossessed",
    4: "Duel",
    6: "Block",
    8: "Offside",
    9: "Clearance",
    10: "Interception",
    14: "Dribble",
    16: "Shot",
    17: "Pressure",
    18: "Half Start",
    19: "Substitution",
    20: "Own Goal Against",
    21: "Foul Won",
    22: "Foul Committed",
    23: "Goal Keeper",
    24: "Bad Behaviour",
    25: "Own Goal For",
    26: "Player On",
    27: "Player Off",
    28: "Shield",
    30: "Pass",
    33: "50/50",
    34: "Half End",
    35: "Starting XI",
    36: "Tactical Shift",
    37: "Error",
    38: "Miscontrol",
    39: "Dribbled Past",
    40: "Injury Stoppage",
    41: "Referee Ball-Drop",
    42: "Ball Receipt*",
    43: "Carry",
}
COMMON_FIELDS = {
    "id",
    "index",
    "period",
    "timestamp",
    "minute",
    "second",
    "type",
    "possession",
    "possession_team",
    "play_pattern",
    "team",
    "player",
    "position",
    "location",
    "duration",
    "under_pressure",
    "counterpress",
    "off_camera",
    "related_events",
}
DETAIL_FIELDS = {
    "50_50",
    "bad_behaviour",
    "ball_receipt",
    "ball_recovery",
    "block",
    "carry",
    "clearance",
    "dribble",
    "duel",
    "foul_committed",
    "foul_won",
    "goalkeeper",
    "half_start",
    "half_end",
    "injury_stoppage",
    "interception",
    "miscontrol",
    "out",
    "pass",
    "player_off",
    "shot",
    "substitution",
    "tactics",
}


def native_id(value):
    if type(value) is not int or value <= 0:
        raise IngestionError("StatsBomb IDs must be positive integers")
    return value


def sb_id(kind, value):
    return make_id("statsbomb", kind, native_id(value))


def optional_id(kind, value):
    return sb_id(kind, value["id"]) if value is not None else None


def name(value):
    return value["name"] if value is not None else None


def boolean(value, key):
    result = value.get(key, False)
    if type(result) is not bool:
        raise IngestionError(f"Unexpected non-boolean source field: {key}")
    return result


def timestamp_seconds(value: str) -> float:
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?", value):
        raise IngestionError("Malformed period timestamp")
    hours, minutes, seconds = value.split(":")
    if int(minutes) >= 60 or float(seconds) >= 60:
        raise IngestionError("Timestamp minute/second out of range")
    return int(hours) * 3600.0 + int(minutes) * 60.0 + float(seconds)


def lineup_point(value: str, period: int) -> PeriodPoint:
    if type(period) is not int or period not in PERIOD_BASE:
        raise IngestionError("Unknown playable lineup period")
    if not isinstance(value, str) or not re.fullmatch(r"\d+:\d{2}(?:\.\d+)?", value):
        raise IngestionError("Malformed lineup clock")
    minutes, seconds = value.split(":")
    if float(seconds) >= 60:
        raise IngestionError("Lineup clock second out of range")
    return PeriodPoint(
        period=period, elapsed_seconds=int(minutes) * 60.0 + float(seconds) - PERIOD_BASE[period]
    )


def location(value):
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 2:
        raise IngestionError("Pitch location must have two coordinates")
    if any(type(v) not in {int, float} for v in value):
        raise IngestionError("Pitch coordinates must be numeric, excluding booleans")
    # StatsBomb actor events already use the team's attacking orientation; no second-half flip.
    return Location(x=value[0] / 120.0, y=value[1] / 80.0)


def map_position(raw):
    flags = []
    try:
        start = lineup_point(raw["from"], raw["from_period"])
    except (IngestionError, ValidationError):
        start = None
        flags.append("INVALID_SOURCE_POSITION_START")
    end = None
    if raw["to"] is not None:
        try:
            end = lineup_point(raw["to"], raw["to_period"])
        except (IngestionError, ValidationError):
            flags.append("INVALID_SOURCE_POSITION_END")
    if start is not None and end is not None:
        if end == start:
            flags.append("ZERO_DURATION_POSITION_OBSERVATION")
        elif end.ordering_key() < start.ordering_key():
            flags.append("REVERSED_SOURCE_POSITION_INTERVAL")
    return PositionObservation(
        source_position_id=raw["position_id"],
        source_position_name=raw["position"],
        start=start,
        end=end,
        start_reason=raw["start_reason"],
        end_reason=raw["end_reason"],
        quality_flags=tuple(flags),
        source_attributes=raw,
    )


def map_card(raw):
    try:
        point = lineup_point(raw["time"], raw["period"])
        flags = ()
    except (IngestionError, ValidationError):
        point = None
        flags = ("INVALID_SOURCE_CARD_CLOCK",)
    return CardObservation(
        time=point,
        card_type=raw["card_type"],
        reason=raw["reason"],
        source_attributes=raw,
        quality_flags=flags,
    )


def map_lineups(rows, match_id, snapshot_id):
    result = []
    for team in rows:
        entries = []
        for raw in team["lineup"]:
            entries.append(
                LineupEntry(
                    player=Player(
                        player_id=sb_id("player", raw["player_id"]),
                        player_name=raw["player_name"],
                        nickname=raw.get("player_nickname"),
                        country=name(raw.get("country")),
                    ),
                    jersey_number=raw.get("jersey_number"),
                    positions=tuple(map_position(p) for p in raw["positions"]),
                    cards=tuple(map_card(c) for c in raw["cards"]),
                    source_attributes={
                        k: v
                        for k, v in raw.items()
                        if k
                        not in {
                            "player_id",
                            "player_name",
                            "player_nickname",
                            "country",
                            "jersey_number",
                            "positions",
                            "cards",
                        }
                    },
                )
            )
        result.append(
            TeamLineup(
                match_id=match_id,
                team=Team(team_id=sb_id("team", team["team_id"]), team_name=team["team_name"]),
                entries=tuple(entries),
                snapshot_id=snapshot_id,
                source_attributes={
                    k: v
                    for k, v in team.items()
                    if k
                    not in {
                        "team_id",
                        "team_name",
                        "lineup",
                    }
                },
            )
        )
    if len(result) != 2 or result[0].team.team_id == result[1].team.team_id:
        raise IngestionError("Expected two distinct team sheets")
    return tuple(result)


def map_event(raw, match_id, snapshot_id):
    kind = raw["type"]["name"]
    flags = []
    if EVENT_TYPES.get(raw["type"]["id"]) != kind:
        flags.append("UNREVIEWED_EVENT_TYPE")
    detail = None
    if kind == "Pass":
        value = raw["pass"]
        outcome = (
            "complete"
            if "outcome" not in value
            else {
                "Incomplete": "incomplete",
                "Out": "out",
                "Pass Offside": "offside",
            }.get(name(value.get("outcome")), "unknown")
        )
        if outcome == "unknown":
            flags.append("UNMAPPED_PASS_OUTCOME")
        detail = PassDetail(
            end_location=location(value.get("end_location")),
            recipient_id=optional_id("player", value.get("recipient")),
            outcome=outcome,
            assisted_shot_id=value.get("assisted_shot_id"),
            goal_assist=boolean(value, "goal_assist"),
            shot_assist=boolean(value, "shot_assist"),
            length_provider_units=value.get("length"),
            angle_radians=value.get("angle"),
            height=name(value.get("height")),
            body_part=name(value.get("body_part")),
            pass_type=name(value.get("type")),
            switch=boolean(value, "switch"),
            cross=boolean(value, "cross"),
        )
    elif kind == "Carry":
        detail = CarryDetail(end_location=location(raw["carry"].get("end_location")))
    elif kind == "Shot":
        value = raw["shot"]
        end = value.get("end_location")
        if end is not None and (not isinstance(end, list) or len(end) not in {2, 3}):
            raise IngestionError("Shot endpoint must have two or three coordinates")
        detail = ShotDetail(
            xg=value.get("statsbomb_xg"),
            outcome=name(value["outcome"]),
            body_part=name(value.get("body_part")),
            shot_type=name(value.get("type")),
            key_pass_id=value.get("key_pass_id"),
            technique=name(value.get("technique")),
            end_location=ShotEndpoint(
                x_provider_units=end[0],
                y_provider_units=end[1],
                z_provider_units=end[2] if len(end) == 3 else None,
            )
            if end
            else None,
        )
    elif kind in {"Duel", "Interception", "Ball Recovery", "Block", "Clearance"}:
        key = {"Ball Recovery": "ball_recovery"}.get(kind, kind.lower())
        value = raw.get(key, {})
        detail = DefensiveDetail(
            subtype=name(value.get("type")),
            outcome=name(value.get("outcome")),
            recovery_failure=boolean(value, "recovery_failure")
            if kind == "Ball Recovery"
            else None,
            offensive=boolean(value, "offensive") if kind in {"Block", "Ball Recovery"} else None,
        )
    extra = {k: v for k, v in raw.items() if k not in COMMON_FIELDS}
    extra["provider_location"] = raw.get("location")
    extra["provider_timestamp"] = raw["timestamp"]
    if set(raw) - COMMON_FIELDS - DETAIL_FIELDS:
        flags.append("UNREVIEWED_SOURCE_FIELDS")
    tactics = raw.get("tactics", {})
    card = raw.get("foul_committed", {}).get("card") or raw.get("bad_behaviour", {}).get("card")
    boundaries = raw.get("half_start", {}) | raw.get("half_end", {})
    boundary_flags = tuple(
        key
        for key in ("late_video_start", "early_video_end", "match_suspended")
        if boolean(boundaries, key)
    )
    return Event(
        match_id=match_id,
        event_id=raw["id"],
        index=raw["index"],
        period=raw["period"],
        elapsed_seconds=timestamp_seconds(raw["timestamp"]),
        display_minute=raw["minute"],
        display_second=raw["second"],
        event_type=kind,
        source_type_id=raw["type"]["id"],
        snapshot_id=snapshot_id,
        possession_id=raw.get("possession"),
        possession_team_id=optional_id("team", raw.get("possession_team")),
        team_id=optional_id("team", raw.get("team")),
        player_id=optional_id("player", raw.get("player")),
        position=name(raw.get("position")),
        start_location=location(raw.get("location")),
        duration_seconds=raw.get("duration"),
        under_pressure=boolean(raw, "under_pressure"),
        counterpress=boolean(raw, "counterpress"),
        off_camera=boolean(raw, "off_camera"),
        related_event_ids=tuple(raw.get("related_events", [])),
        detail=detail,
        play_pattern=name(raw.get("play_pattern")),
        quality_flags=tuple(flags),
        source_attributes=extra,
        formation=str(tactics["formation"]) if "formation" in tactics else None,
        tactical_lineup=tuple(
            TacticalPlayer(
                player_id=sb_id("player", p["player"]["id"]),
                source_position_id=p["position"]["id"],
                position_name=p["position"]["name"],
                jersey_number=p.get("jersey_number"),
            )
            for p in tactics.get("lineup", [])
        ),
        replacement_player_id=optional_id("player", raw.get("substitution", {}).get("replacement")),
        card=EventCard(source_card_id=card["id"], card_type=card["name"]) if card else None,
        player_off_permanent=boolean(raw.get("player_off", {}), "permanent")
        if kind == "Player Off"
        else None,
        period_boundary_flags=boundary_flags,
    )


class StatsBombOpenDataProvider(EventProvider):
    def __init__(self, store: SnapshotStore, settings: DatasetSettings):
        if store.revision != settings.revision:
            raise IngestionError("Provider/store revisions differ")
        self.store = store
        self.settings = settings
        self._catalog = None
        self._matches = None

    @property
    def provider_id(self):
        return "statsbomb"

    def list_competition_seasons(self):
        if self._catalog is None:
            rows, artifact = self.store.read("data/competitions.json", self.settings.catalog_sha256)
            self._catalog = tuple(
                CompetitionSeason(
                    competition=Competition(
                        competition_id=sb_id("competition", r["competition_id"]),
                        competition_name=r["competition_name"],
                        country=r["country_name"],
                        gender=r["competition_gender"],
                        youth=r["competition_youth"],
                        international=r["competition_international"],
                    ),
                    season=Season(
                        season_id=sb_id("season", r["season_id"]), season_name=r["season_name"]
                    ),
                    snapshot_id=artifact.snapshot.snapshot_id,
                )
                for r in rows
            )
            ids = [(c.competition.competition_id, c.season.season_id) for c in self._catalog]
            if len(ids) != len(set(ids)):
                raise IngestionError("Duplicate competition-season IDs")
        return self._catalog

    def list_matches(self, competition_id, season_id):
        if (competition_id, season_id) != (
            sb_id("competition", self.settings.competition_id),
            sb_id("season", self.settings.season_id),
        ):
            raise IngestionError("This provider instance is scoped to its configured cohort")
        if self._matches is None:
            selected = [
                c
                for c in self.list_competition_seasons()
                if (c.competition.competition_id, c.season.season_id) == (competition_id, season_id)
            ]
            if len(selected) != 1:
                raise IngestionError("Configured cohort missing from pinned catalog")
            if (selected[0].competition.competition_name, selected[0].season.season_name) != (
                self.settings.competition_name,
                self.settings.season_name,
            ):
                raise IngestionError("Configured cohort labels differ from audited catalog")
            path = f"data/matches/{self.settings.competition_id}/{self.settings.season_id}.json"
            rows, artifact = self.store.read(path, self.settings.matches_sha256)
            matches = []
            for r in rows:
                if (r["competition"]["competition_id"], r["season"]["season_id"]) != (
                    self.settings.competition_id,
                    self.settings.season_id,
                ):
                    raise IngestionError("Match references a different competition/season")
                matches.append(
                    Match(
                        match_id=sb_id("match", r["match_id"]),
                        competition_id=competition_id,
                        season_id=season_id,
                        match_date=r["match_date"],
                        home_team_id=sb_id("team", r["home_team"]["home_team_id"]),
                        away_team_id=sb_id("team", r["away_team"]["away_team_id"]),
                        home_score=r["home_score"],
                        away_score=r["away_score"],
                        stage=r["competition_stage"]["name"],
                        data_version=r["metadata"]["data_version"],
                        snapshot_id=artifact.snapshot.snapshot_id,
                        source_attributes={
                            k: v
                            for k, v in r.items()
                            if k
                            not in {
                                "match_id",
                                "competition",
                                "season",
                                "match_date",
                                "home_score",
                                "away_score",
                            }
                        },
                    )
                )
            if len(matches) != len({m.match_id for m in matches}):
                raise IngestionError("Duplicate match IDs")
            self._matches = tuple(sorted(matches, key=lambda m: int(m.match_id.rsplit(":", 1)[1])))
        return self._matches

    def _native_match(self, match_id):
        if self._matches is None or match_id not in {m.match_id for m in self._matches}:
            raise IngestionError("Match is not in the verified configured cohort")
        return int(match_id.rsplit(":", 1)[1])

    def load_events(self, match_id):
        rows, artifact = self.store.read(f"data/events/{self._native_match(match_id)}.json")
        return tuple(map_event(r, match_id, artifact.snapshot.snapshot_id) for r in rows)

    def load_lineups(self, match_id):
        rows, artifact = self.store.read(f"data/lineups/{self._native_match(match_id)}.json")
        return map_lineups(rows, match_id, artifact.snapshot.snapshot_id)
