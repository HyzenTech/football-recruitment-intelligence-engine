"""Explicit unknown age; no statistics or recruitment ranking are implemented here."""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import Field

from football_recruitment.domain.models import Contract, Player


class Eligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


class AgeConstraint(Contract):
    max_age: Annotated[int, Field(ge=0, strict=True)]
    as_of: date

    def evaluate(self, player: Player) -> Eligibility:
        """Age is measured on a declared date; unknown DOB never passes the filter."""
        born = player.birth_date
        if born is None:
            return Eligibility.UNKNOWN
        if born > self.as_of:
            raise ValueError("Birth date is after the eligibility reference date")
        age = (
            self.as_of.year
            - born.year
            - ((self.as_of.month, self.as_of.day) < (born.month, born.day))
        )
        return Eligibility.ELIGIBLE if age <= self.max_age else Eligibility.INELIGIBLE
