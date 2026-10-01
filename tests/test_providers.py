import pytest

from football_recruitment.providers.base import (
    Capability,
    EventProvider,
    MetadataProvider,
    UnsupportedCapabilityError,
    provider_capabilities,
    require_capability,
)


class SyntheticMetadata(MetadataProvider):
    # A dishonest/inaccurate provider flag must not override the interface.
    capabilities = {Capability.EVENTS}

    @property
    def provider_id(self):
        return "synthetic"

    def list_competition_seasons(self):
        return ()

    def list_matches(self, competition_id, season_id):
        return ()


def test_eventless_provider_cannot_claim_event_capability():
    source = SyntheticMetadata()
    assert provider_capabilities(source) == {Capability.COMPETITIONS, Capability.MATCHES}
    with pytest.raises(UnsupportedCapabilityError, match="does not support events"):
        require_capability(source, Capability.EVENTS)


def test_event_provider_requires_both_event_and_lineup_implementations():
    class IncompleteEventSource(EventProvider, SyntheticMetadata):
        def load_events(self, match_id):
            return ()

    with pytest.raises(TypeError, match="load_lineups"):
        IncompleteEventSource()


def test_complete_event_interface_advertises_required_capabilities():
    class CompleteEventSource(EventProvider, SyntheticMetadata):
        def load_events(self, match_id):
            return ()

        def load_lineups(self, match_id):
            return ()

    source = CompleteEventSource()
    assert provider_capabilities(source) == set(Capability)
    require_capability(source, Capability.LINEUPS)
