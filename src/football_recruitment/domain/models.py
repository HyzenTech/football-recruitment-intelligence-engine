"""Strict canonical records. Schema validation is not season-wide data certification."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, JsonValue, model_validator

from football_recruitment.domain.ids import CompetitionId, MatchId, PlayerId, SeasonId, TeamId

NonEmpty = Annotated[str, Field(min_length=1)]
NonNegative = Annotated[float, Field(ge=0, strict=True)]
Positive = Annotated[float, Field(gt=0, strict=True)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Contract(BaseModel):
    """Forbid unnoticed fields and non-finite numbers at the canonical boundary."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
        validate_default=True,
    )


class QualityStatus(StrEnum):
    UNVALIDATED = "UNVALIDATED"
    VALIDATED = "VALIDATED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    EXCLUDED = "EXCLUDED"


class PositionGroup(StrEnum):
    GK = "GK"
    CB = "CB"
    FB = "FB"
    DM = "DM"
    CM = "CM"
    AM = "AM"
    W = "W"
    ST = "ST"


class ProviderSnapshot(Contract):
    snapshot_id: NonEmpty
    provider: NonEmpty
    revision: NonEmpty
    retrieved_at: datetime
    source_url: HttpUrl
    sha256: Sha256
    license_url: HttpUrl
    schema_version: NonEmpty

    @model_validator(mode="after")
    def require_timezone(self) -> Self:
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("Snapshot retrieval time must include a timezone")
        return self


class Competition(Contract):
    competition_id: CompetitionId
    competition_name: NonEmpty
    country: NonEmpty
    gender: Literal["female", "male", "mixed", "unknown"] = "unknown"
    youth: bool | None = None
    international: bool | None = None


class Season(Contract):
    season_id: SeasonId
    season_name: NonEmpty


class CompetitionSeason(Contract):
    competition: Competition
    season: Season
    snapshot_id: NonEmpty
    coverage_notes: str | None = None


class Team(Contract):
    team_id: TeamId
    team_name: NonEmpty


class Player(Contract):
    player_id: PlayerId
    player_name: NonEmpty
    nickname: str | None = None
    country: str | None = None
    birth_date: date | None = None
    birth_date_source: HttpUrl | None = None

    @model_validator(mode="after")
    def require_birth_date_evidence(self) -> Self:
        if (self.birth_date is None) != (self.birth_date_source is None):
            raise ValueError("Birth date and its evidence must both be present or both absent")
        return self


class Match(Contract):
    match_id: MatchId
    competition_id: CompetitionId
    season_id: SeasonId
    match_date: date
    home_team_id: TeamId
    away_team_id: TeamId
    home_score: Annotated[int, Field(ge=0, strict=True)] | None = None
    away_score: Annotated[int, Field(ge=0, strict=True)] | None = None
    stage: str | None = None
    data_version: NonEmpty
    snapshot_id: NonEmpty
    source_attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_distinct_teams_and_complete_score(self) -> Self:
        if self.home_team_id == self.away_team_id:
            raise ValueError("A match must have two distinct teams")
        if (self.home_score is None) != (self.away_score is None):
            raise ValueError("Score must be complete or unknown for both teams")
        return self


class MatchRoster(Contract):
    match_id: MatchId
    team_id: TeamId
    player_id: PlayerId
    jersey_number: PositiveInt | None = None
    status: Literal["starter", "substitute", "unused", "unknown"] = "unknown"


class PeriodPoint(Contract):
    """Elapsed seconds within a playable period, never a global match-clock minute."""

    period: Annotated[int, Field(ge=1, le=4, strict=True)]
    elapsed_seconds: NonNegative

    def ordering_key(self) -> tuple[int, float]:
        return self.period, self.elapsed_seconds


class MatchPeriod(Contract):
    match_id: MatchId
    period: Annotated[int, Field(ge=1, le=4, strict=True)]
    duration_seconds: Positive
    nominal_base_seconds: NonNegative
    quality_status: QualityStatus = QualityStatus.UNVALIDATED


class PresenceInterval(Contract):
    match_id: MatchId
    team_id: TeamId
    player_id: PlayerId
    start: PeriodPoint
    end: PeriodPoint
    start_reason: NonEmpty
    end_reason: NonEmpty
    evidence_event_ids: tuple[str, ...] = ()
    quality_status: QualityStatus = QualityStatus.UNVALIDATED

    @model_validator(mode="after")
    def require_forward_interval(self) -> Self:
        if self.end.ordering_key() <= self.start.ordering_key():
            raise ValueError("An interval must end after its start")
        return self


class PositionInterval(PresenceInterval):
    source_position_id: PositiveInt
    source_position_name: NonEmpty
    position_group: PositionGroup
    mapping_version: NonEmpty


class PositionObservation(Contract):
    """Source position segment with an unresolved final boundary; not validated minutes."""

    source_position_id: PositiveInt
    source_position_name: NonEmpty
    start: PeriodPoint | None
    end: PeriodPoint | None = None
    start_reason: NonEmpty
    end_reason: NonEmpty
    quality_flags: tuple[str, ...] = ()
    source_attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_order_if_end_known(self) -> Self:
        if self.start is None and "INVALID_SOURCE_POSITION_START" not in self.quality_flags:
            raise ValueError("Unparseable source start requires an explicit quality flag")
        if (
            self.start is not None
            and self.end is not None
            and (self.end.ordering_key() < self.start.ordering_key())
            and "REVERSED_SOURCE_POSITION_INTERVAL" not in self.quality_flags
        ):
            raise ValueError("Reversed source observation requires an explicit quality flag")
        if (
            self.start is not None
            and self.end is not None
            and (self.end.ordering_key() == self.start.ordering_key())
        ):
            if "ZERO_DURATION_POSITION_OBSERVATION" not in self.quality_flags:
                raise ValueError("Zero-duration source position requires an explicit quality flag")
        return self


class CardObservation(Contract):
    time: PeriodPoint | None
    card_type: NonEmpty
    reason: NonEmpty
    source_attributes: dict[str, JsonValue] = Field(default_factory=dict)
    quality_flags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_clock_flag(self) -> Self:
        if self.time is None and "INVALID_SOURCE_CARD_CLOCK" not in self.quality_flags:
            raise ValueError("Unparseable card clock requires an explicit quality flag")
        return self


class LineupEntry(Contract):
    player: Player
    jersey_number: PositiveInt | None = None
    positions: tuple[PositionObservation, ...] = ()
    cards: tuple[CardObservation, ...] = ()
    source_attributes: dict[str, JsonValue] = Field(default_factory=dict)
    # Empty positions can mean an unused substitute; never infer an appearance from roster alone.


class TeamLineup(Contract):
    match_id: MatchId
    team: Team
    entries: tuple[LineupEntry, ...]
    snapshot_id: NonEmpty
    source_attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_unique_players(self) -> Self:
        ids = [entry.player.player_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate player ID on a team sheet")
        return self


class Appearance(Contract):
    match_id: MatchId
    team_id: TeamId
    player_id: PlayerId
    starter: bool
    starting_position: str | None = None
    playing_seconds: NonNegative | None = None
    nominal_minutes: NonNegative | None = None
    minutes_method: str | None = None
    minutes_version: str | None = None
    quality_status: QualityStatus = QualityStatus.UNVALIDATED
    quality_flags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_validated_minutes_provenance(self) -> Self:
        if self.quality_status == QualityStatus.VALIDATED:
            if self.playing_seconds is None or self.playing_seconds <= 0:
                raise ValueError("A validated appearance requires positive playing seconds")
            if not self.minutes_method or not self.minutes_version:
                raise ValueError("Validated minutes require method and version")
        return self


class Location(Contract):
    """Normalized team-relative coordinates; deliberately not metres."""

    x: Annotated[float, Field(ge=0, le=1, strict=True)]
    y: Annotated[float, Field(ge=0, le=1, strict=True)]
    frame: Literal["actor_team_attacks_positive_x"] = "actor_team_attacks_positive_x"


class PassDetail(Contract):
    kind: Literal["pass"] = "pass"
    end_location: Location | None = None
    recipient_id: PlayerId | None = None
    outcome: Literal["complete", "incomplete", "out", "offside", "unknown"]
    assisted_shot_id: str | None = None
    goal_assist: bool | None = None
    shot_assist: bool | None = None
    length_provider_units: NonNegative | None = None
    angle_radians: float | None = None
    height: str | None = None
    body_part: str | None = None
    pass_type: str | None = None
    switch: bool | None = None
    cross: bool | None = None


class CarryDetail(Contract):
    kind: Literal["carry"] = "carry"
    end_location: Location | None = None


class ShotEndpoint(Contract):
    """Shot end coordinates in provider grid units; height is a separate dimension."""

    x_provider_units: float
    y_provider_units: float
    z_provider_units: float | None = None


class ShotDetail(Contract):
    kind: Literal["shot"] = "shot"
    xg: Annotated[float, Field(ge=0, le=1, strict=True)] | None = None
    outcome: NonEmpty
    body_part: str | None = None
    shot_type: str | None = None
    key_pass_id: str | None = None
    end_location: ShotEndpoint | None = None
    technique: str | None = None


class DefensiveDetail(Contract):
    kind: Literal["defensive"] = "defensive"
    subtype: str | None = None
    outcome: str | None = None
    recovery_failure: bool | None = None
    offensive: bool | None = None


EventDetail = Annotated[
    PassDetail | CarryDetail | ShotDetail | DefensiveDetail, Field(discriminator="kind")
]


class TacticalPlayer(Contract):
    player_id: PlayerId
    source_position_id: PositiveInt
    position_name: NonEmpty
    jersey_number: PositiveInt | None = None


class EventCard(Contract):
    source_card_id: PositiveInt
    card_type: NonEmpty


class Event(Contract):
    match_id: MatchId
    event_id: NonEmpty
    index: PositiveInt
    period: Annotated[int, Field(ge=1, le=5, strict=True)]
    elapsed_seconds: NonNegative
    display_minute: Annotated[int, Field(ge=0, strict=True)]
    display_second: Annotated[int, Field(ge=0, lt=60, strict=True)]
    event_type: NonEmpty
    source_type_id: PositiveInt
    snapshot_id: NonEmpty
    possession_id: PositiveInt | None = None
    possession_team_id: TeamId | None = None
    team_id: TeamId | None = None
    player_id: PlayerId | None = None
    position: str | None = None
    start_location: Location | None = None
    duration_seconds: NonNegative | None = None
    under_pressure: bool | None = None
    counterpress: bool | None = None
    off_camera: bool | None = None
    related_event_ids: tuple[str, ...] = ()
    detail: EventDetail | None = None
    play_pattern: str | None = None
    quality_flags: tuple[str, ...] = ()
    source_attributes: dict[str, JsonValue] = Field(default_factory=dict)
    formation: str | None = None
    tactical_lineup: tuple[TacticalPlayer, ...] = ()
    replacement_player_id: PlayerId | None = None
    card: EventCard | None = None
    player_off_permanent: bool | None = None
    period_boundary_flags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_consistent_actor_and_detail(self) -> Self:
        if self.player_id is not None and self.team_id is None:
            raise ValueError("A player-attributed event requires a team")
        expected = {"Pass": "pass", "Carry": "carry", "Shot": "shot"}.get(self.event_type)
        if expected and (self.detail is None or self.detail.kind != expected):
            raise ValueError(f"{self.event_type} requires its matching typed detail")
        if self.detail and self.detail.kind in {"pass", "carry", "shot"}:
            if expected != self.detail.kind:
                raise ValueError("Event type and detail do not match")
        return self
