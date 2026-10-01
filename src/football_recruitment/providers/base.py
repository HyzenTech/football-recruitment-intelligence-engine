"""Separate metadata-only sources from sources that can supply events and lineups."""

from abc import ABC, abstractmethod
from enum import StrEnum

from football_recruitment.domain.models import CompetitionSeason, Event, Match, TeamLineup


class Capability(StrEnum):
    COMPETITIONS = "competitions"
    MATCHES = "matches"
    EVENTS = "events"
    LINEUPS = "lineups"


class UnsupportedCapabilityError(ValueError):
    """The source cannot supply this data; this does not mean zero performance."""


class MetadataProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable source namespace."""

    @abstractmethod
    def list_competition_seasons(self) -> tuple[CompetitionSeason, ...]:
        """Return canonical catalog records with source snapshot references."""

    @abstractmethod
    def list_matches(self, competition_id: str, season_id: str) -> tuple[Match, ...]:
        """Return canonical matches within an explicitly selected cohort."""


class EventProvider(MetadataProvider):
    @abstractmethod
    def load_events(self, match_id: str) -> tuple[Event, ...]:
        """Return canonical events, preserving period and type-specific details."""

    @abstractmethod
    def load_lineups(self, match_id: str) -> tuple[TeamLineup, ...]:
        """Preserve roster and unresolved position observations, without asserting minutes."""


def provider_capabilities(provider: MetadataProvider) -> frozenset[Capability]:
    """Derive capability from enforceable interfaces, not a provider's self-reported flags."""
    capabilities = {Capability.COMPETITIONS, Capability.MATCHES}
    if isinstance(provider, EventProvider):
        capabilities.update({Capability.EVENTS, Capability.LINEUPS})
    return frozenset(capabilities)


def require_capability(provider: MetadataProvider, capability: Capability) -> None:
    """Fail before a missing source is interpreted as an empty observed dataset."""
    if capability not in provider_capabilities(provider):
        raise UnsupportedCapabilityError(f"{provider.provider_id} does not support {capability}")
