"""Namespaced identity prevents unrelated provider integers from colliding."""

import re
from functools import partial
from typing import Annotated, Literal

from pydantic import AfterValidator, StringConstraints

EntityKind = Literal["competition", "season", "team", "player", "match"]
ID_PATTERN = r"^[a-z][a-z0-9_-]*:(competition|season|team|player|match):[A-Za-z0-9_.-]+$"
NamespacedId = Annotated[str, StringConstraints(pattern=ID_PATTERN)]


def validate_kind(value: str, *, kind: EntityKind) -> str:
    """Reject a valid ID that names the wrong entity type."""
    if value.split(":")[1] != kind:
        raise ValueError(f"Expected a {kind} ID")
    return value


def make_id(provider: str, kind: EntityKind, native_id: int | str) -> str:
    """Preserve provider-native identity without name-based cross-provider merging."""
    if isinstance(native_id, bool) or not isinstance(native_id, int | str):
        raise ValueError("Native ID must be an integer or string, excluding booleans")
    value = f"{provider}:{kind}:{native_id}"
    if not re.fullmatch(ID_PATTERN, value):
        raise ValueError("Invalid provider, entity kind or native identifier")
    return value


CompetitionId = Annotated[NamespacedId, AfterValidator(partial(validate_kind, kind="competition"))]
SeasonId = Annotated[NamespacedId, AfterValidator(partial(validate_kind, kind="season"))]
TeamId = Annotated[NamespacedId, AfterValidator(partial(validate_kind, kind="team"))]
PlayerId = Annotated[NamespacedId, AfterValidator(partial(validate_kind, kind="player"))]
MatchId = Annotated[NamespacedId, AfterValidator(partial(validate_kind, kind="match"))]
