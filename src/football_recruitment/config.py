"""Load and validate local versioned configuration without fetching or creating data."""

import tomllib
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, Self

from pydantic import Field, HttpUrl, model_validator

from football_recruitment.domain.models import (
    Contract,
    NonNegative,
    PositionGroup,
    Positive,
    PositiveInt,
    Sha256,
)
from football_recruitment.providers.base import Capability


class DataPaths(Contract):
    raw: str
    interim: str
    processed: str
    reports: str

    @model_validator(mode="after")
    def require_relative_workspace_paths(self) -> Self:
        values = (self.raw, self.interim, self.processed, self.reports)
        normalized = []
        for value in values:
            path = PurePosixPath(value.replace("\\", "/"))
            if not value or path.is_absolute() or PureWindowsPath(value).drive:
                raise ValueError("Data paths must be relative to the project")
            if ".." in path.parts or str(path) == ".":
                raise ValueError("Data paths cannot escape or equal the project root")
            # Keep paths unambiguous on case-insensitive Windows filesystems too.
            normalized.append(PurePosixPath(str(path).casefold()))
        if len(set(normalized)) != len(values):
            raise ValueError("Data stages must have distinct paths")
        if any(a in b.parents for a in normalized for b in normalized if a != b):
            raise ValueError("Data stages cannot be nested inside each other")
        return self


class DatasetSettings(Contract):
    schema_version: Literal["1.0"]
    provider: Literal["statsbomb"]
    competition_id: Annotated[int, Field(gt=0, strict=True)]
    season_id: Annotated[int, Field(gt=0, strict=True)]
    competition_name: str
    season_name: str
    repository: Literal["https://github.com/hudl/open-data"]
    revision: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    catalog_sha256: Sha256
    matches_sha256: Sha256
    expected_match_count: Annotated[int, Field(gt=0, strict=True)]
    expected_team_count: Annotated[int, Field(gt=1, strict=True)]
    audit_date: date
    usage: Literal["noncommercial_research"]
    data_license_url: HttpUrl
    required_capabilities: tuple[Capability, ...]
    unavailable_fields: tuple[str, ...]
    paths: DataPaths

    @model_validator(mode="after")
    def require_pinned_license_and_unique_capabilities(self) -> Self:
        expected = f"{self.repository}/blob/{self.revision}/LICENSE.pdf"
        if str(self.data_license_url) != expected:
            raise ValueError("Data licence must reference the same pinned revision")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("Duplicate required provider capabilities")
        return self


class MetricSettings(Contract):
    schema_version: Literal["1.0"]
    definition_version: str
    status: Literal["PROVISIONAL", "IMPLEMENTED"]
    open_play_patterns: tuple[str, ...] = ("Regular Play", "From Counter")
    long_pass_minimum_yards: Positive = 30.0
    provider_pitch_length: Positive
    provider_pitch_width: Positive
    distance_units: Literal["provider_grid_units"]
    progression_absolute_reduction: Positive
    progression_relative_reduction: Annotated[float, Field(gt=0, le=1, strict=True)]
    progression_requires_forward: bool
    pass_progression_requires_completion: bool
    progression_open_play_only: bool
    final_third_start_x: Positive
    penalty_area_start_x: Positive
    penalty_area_y_min: NonNegative
    penalty_area_y_max: Positive

    @model_validator(mode="after")
    def require_valid_zones(self) -> Self:
        if (
            not 0
            < self.final_third_start_x
            < self.penalty_area_start_x
            < self.provider_pitch_length
        ):
            raise ValueError("Zone x boundaries must be ordered inside the pitch")
        if not 0 <= self.penalty_area_y_min < self.penalty_area_y_max <= self.provider_pitch_width:
            raise ValueError("Penalty area y boundaries must be ordered inside the pitch")
        return self


class CohortSettings(Contract):
    schema_version: Literal["1.0"]
    status: Literal["PROVISIONAL", "IMPLEMENTED"]
    minimum_minutes: Positive
    minimum_peer_count: Annotated[int, Field(ge=2, strict=True)]
    minutes_convention: Literal["elapsed_including_stoppage", "nominal_regulation"]
    unknown_minutes_policy: Literal["exclude"]
    unknown_birth_date_policy: Literal["exclude_from_age_filtered_queries"]
    small_cohort_policy: Literal["suppress_percentiles_and_ranking"]
    role_mapping_version: str
    dominant_role_minimum_share: Annotated[float, Field(gt=0.5, le=1, strict=True)]
    position_groups: dict[PositionGroup, tuple[PositiveInt, ...]]

    @model_validator(mode="after")
    def require_complete_disjoint_position_groups(self) -> Self:
        if set(self.position_groups) != set(PositionGroup):
            raise ValueError("All eight broad comparison groups must be explicitly mapped")
        positions = [p for ids in self.position_groups.values() for p in ids]
        if any(isinstance(p, bool) for ids in self.position_groups.values() for p in ids):
            raise ValueError("Position IDs cannot be booleans")
        if len(positions) != len(set(positions)) or set(positions) != set(range(1, 26)):
            raise ValueError("Position IDs 1..25 must each occur exactly once")
        return self


class RankingRequirement(Contract):
    name: Annotated[str, Field(min_length=1)]
    position_group: PositionGroup
    minimum_minutes: Positive = 450.0
    top_k: Annotated[int, Field(ge=1, le=100, strict=True)] = 10
    excluded_team_ids: tuple[str, ...] = ()
    weights: dict[str, NonNegative]
    maximum_age: None = None
    maximum_market_value: None = None
    contract_expiry_before: None = None

    @model_validator(mode="after")
    def require_supported_positive_weights(self) -> Self:
        from football_recruitment.features.metrics import MEANS, METRICS

        if not self.weights or not set(self.weights) <= set(METRICS) - set(MEANS):
            raise ValueError("Ranking weights must reference direction-aware implemented metrics")
        if not any(w > 0 for w in self.weights.values()):
            raise ValueError("Ranking weights must have a positive total")
        if self.position_group == PositionGroup.GK and not set(self.weights) <= {
            "passes_attempted",
            "passes_completed",
            "pass_completion_pct",
            "long_passes",
        }:
            raise ValueError("Goalkeeper ranking supports distribution metrics only")
        return self


class RankingSettings(Contract):
    schema_version: Literal["1.0"]
    definition_version: Literal["ranking-0.7.0"]
    status: Literal["IMPLEMENTED"]
    method: Literal["weighted_peer_percentiles"]
    missing_feature_policy: Literal["require_common_complete_feature_set"]
    age_filter_enabled: Literal[False]
    market_value_filter_enabled: Literal[False]
    weights: dict[str, float]
    requirements: dict[str, RankingRequirement]

    @model_validator(mode="after")
    def require_named_requirements(self) -> Self:
        if self.weights:
            raise ValueError("Use named requirements rather than global weights")
        if not self.requirements or any(not name for name in self.requirements):
            raise ValueError("At least one named ranking requirement is required")
        return self


class SimilaritySettings(Contract):
    schema_version: Literal["1.0"]
    definition_version: Literal["similarity-0.6.0"]
    status: Literal["IMPLEMENTED"]
    scaling: Literal["standard", "robust"]
    default_top_k: Annotated[int, Field(ge=1, le=50, strict=True)]
    missing_feature_policy: Literal["require_fixed_complete_vector"]
    features: dict[PositionGroup, tuple[str, ...]]

    @model_validator(mode="after")
    def require_complete_unique_features(self) -> Self:
        from football_recruitment.features.metrics import METRICS

        if set(self.features) != set(PositionGroup):
            raise ValueError("Similarity must define all eight position groups")
        for metrics in self.features.values():
            if not metrics or len(set(metrics)) != len(metrics) or not set(metrics) <= set(METRICS):
                raise ValueError("Similarity features must be nonempty, unique implemented metrics")
        if not set(self.features[PositionGroup.GK]) <= {
            "passes_attempted",
            "long_passes",
            "passes_completed",
            "pass_completion_pct",
        }:
            raise ValueError("Goalkeeper similarity supports distribution metrics only")
        return self


class ProjectSettings(Contract):
    dataset: DatasetSettings
    metrics: MetricSettings
    cohorts: CohortSettings
    ranking: RankingSettings
    similarity: SimilaritySettings


def load_settings(config_dir: Path) -> ProjectSettings:
    """Read five TOML files; no token, network, cache or data writes are involved."""
    sections = {}
    for section, filename in (
        ("dataset", "dataset.toml"),
        ("metrics", "metrics.toml"),
        ("cohorts", "cohorts.toml"),
        ("ranking", "ranking.toml"),
        ("similarity", "similarity.toml"),
    ):
        with (config_dir / filename).open("rb") as source:
            sections[section] = tomllib.load(source)
    return ProjectSettings.model_validate(sections)
