# Recruitment ranking - ranking-0.7.0

Implemented requirement-specific rankings over verified Phase 5 profiles. A recruitment score describes matching declared event-metric priorities within a historical positional cohort. It is not a universal ability rating, transfer recommendation or prediction of tactical success.

## Requirements

`config/ranking.toml` contains eight illustrative named requirements, one per broad position. Their weights are project conventions, not learned or validated scouting preferences. The global weights remain empty because there is no global player rating. Requirements can also be supplied as strict JSON:

```json
{
  "name": "CB defensive activity with distribution",
  "position_group": "CB",
  "minimum_minutes": 450.0,
  "top_k": 10,
  "excluded_team_ids": [],
  "weights": {
    "interceptions": 3.0,
    "tackles": 2.0,
    "long_passes": 1.0
  }
}
```

Weights must be finite, nonnegative and have a positive total. Zero-weight metrics are exposed as ignored and do not affect completeness. Supported components are implemented direction-aware metrics; descriptive means cannot be ranked. GK requirements accept distribution metrics only. `top_k` is 1..100. A requirement may raise the minutes minimum, but cannot lower the minimum used to verify the profiles. To use a lower base threshold, rebuild and verify the profile cohort explicitly.

Age, market value and contract evidence are absent. Non-null `maximum_age`, `maximum_market_value` or `contract_expiry_before` values fail validation; unknown request fields also fail. These constraints are never silently ignored. Requirements cannot enable unsupported filters in configuration.

## Common peer population

Start with eligible full-player-season profiles in the requested position. Select one team spell per player, using greatest denominator minutes and ascending team ID for ties. Select before completeness filtering; do not substitute a shorter complete spell for an incomplete selected spell. Missing any active component excludes the entire player. All component percentiles then use exactly this common complete population. Exclusions expose reasons and missing metric names; comparisons do not fill nulls with zero or reweight each player differently.

At least ten complete peers are required. Constant active components suppress the whole requirement, with explicit metric names; their weights are not redistributed. Reference IDs and population size are exposed. Candidates are part of the reference population, so rankings use population percentiles rather than leave-one-out percentiles.

Requirement-specific minimum minutes and excluded-team filters apply to candidates after the reference population is formed. They do not refit peer percentiles. This keeps the benchmark fixed when excluding a club or restricting shortlist exposure. Team-spell selection still happens first; a filtered selected spell does not fall back to another team. No candidates produces a labelled empty result, while a shortlist smaller than requested produces fewer results and a warning.

## Formula and explanation

For each active metric, use its profile value: per-90 for counts/sums, raw completion percentage for percentages. Compute `100*(count_less + 0.5*count_equal)/n`. Miscontrols and dispossessions use `100 - percentile`; other metrics use the higher direction. Exact observed ties share a percentile.

Normalize weights by their total (implemented through maximum-weight scaling to avoid overflow). Component contribution is `normalized_weight * percentile`. Recruitment score is the sum of those contributions. All metrics, directions, units, completeness, normalized weights, percentiles and contributions are returned. Arithmetic does not assert that greater event volume means better football.

Sort by descending score, then player ID and team ID at full precision. Ranks are deterministic ordinal positions; equal scores remain equal but their displayed order follows IDs. `ranking_reasons` selects the three largest contributions. `weaker_dimensions` selects the three lowest percentiles among the requested components. These are relative trade-offs within the requirement; unselected dimensions and real-world availability remain unknown. A candidate with one low percentile can still rank highly because priorities differ.

## Commands and verification

```console
uv run --locked fre build-rankings --manifest <profile_manifest_path>
uv run --locked fre verify-rankings --manifest <ranking_manifest_path>
uv run --locked fre rank-players --manifest <profile_manifest_path> --preset CB_defensive_activity
uv run --locked fre rank-players --manifest <profile_manifest_path> --requirement <request.json>
```

The public pure function is `rank_players(profiles, requirement, settings)`; callers must supply verified profiles. CLI commands verify upstream artifacts. Batch builds persist rankings and sensitivity diagnostics with hashes and settings. Verification replays both outputs, report metadata and configuration from verified profiles. It does not establish expert scouting accuracy.

Sensitivity diagnostics increase each active weight by 50% individually, renormalize all weights, and rerank. They also raise candidate minimum minutes to at least 600 while retaining the reference benchmark. Top-five overlap is shared players divided by the baseline top-five count. Mean absolute rank shift is measured only for shared players in the two top-five lists; replacement effects are represented by overlap. Unavailable scenarios stay labelled. These limited deterministic experiments are not confidence intervals or broad robustness guarantees. [Phase 7 results](PHASE_7.md) record actual outcomes; repeated cohort diagnostics are recorded in [Phase 8](PHASE_8.md), while external scouting validation remains unperformed.
