# Evaluation and acceptance gates

## Phase 1

Clean locked installation; package import outside source checkout; meaningful canonical/provider/config tests; lint and format checks; installable distribution verification; no credentials, raw payloads or generated caches in tracked files. These checks verify the foundation, not football analytics. Actual run results are recorded in [Phase 1 checkpoint](PHASE_1.md).

Synthetic tests cover ID collisions/type mismatches, unknown-age rejection, birth-date evidence/birthday boundaries, unsupported event capabilities, unresolved lineup positions versus validated minutes, chronological intervals including period resets, conditional event fields, finite/coordinate validation, pinned config, role mapping and CLI behavior. Raw provider rows are not test fixtures.

## Phase 2

Pinned full-cohort ingestion, deterministic offline cache reuse and independent artifact verification are implemented. 77 synthetic tests exercise mapping/storage failure boundaries. See [Phase 2 checkpoint](PHASE_2.md) for actual cohort counts and unresolved quality flags. Integrity checks do not certify minutes.

## Phase 3

Appearance/minute reconstruction and independent processed verification are implemented. 107 synthetic tests cover calculation, quality and artifact failure boundaries. Full-cohort results and explicit exclusions are recorded in [Phase 3 checkpoint](PHASE_3.md). Correct minute denominators do not establish feature-specific validity.

## Phase 4

41 metric definitions and quality-gated match/season aggregation are implemented and tested against exact synthetic cases. See [Phase 4 checkpoint](PHASE_4.md). Artifact reproducibility is separate from football plausibility or predictive quality.

## Remaining phase gates

Phase 5 acceptance is recorded in [the checkpoint](PHASE_5.md): positional exposure, ties, transfer deduplication, missing/constant metrics, common category populations, explicit exclusions and rehashed tampering.

- Phase 6: completed geometry, self-exclusion, deterministic ties, completeness and replay checks, plus scaling/minute/ablation/subsample diagnostics. See [results](PHASE_6.md).
- Phase 7: exact weighted common-population rankings, filters, exclusions and replay pass; declared weight/minute diagnostics are recorded in [results](PHASE_7.md).
- Phase 8: combined checks, twenty reproducible cohort perturbations and data-only football sanity cases are complete; expert/film-based and predictive validation remain unperformed. See [results](PHASE_8.md).
- Phase 9: interface can query validated outputs; no unsupported age/value controls or fabricated fallback statistics.

Football archetype/sanity review is separate from technical tests and must be grounded in available evidence. Do not claim predictive scouting accuracy, objective player quality or season-wide data certification from passing schema tests.

## Phase 8 protocol

```console
uv run --locked fre build-evaluation --manifest <profile_manifest_path> --replicates 20
uv run --locked fre verify-evaluation --manifest <evaluation_manifest_path>
```

The build verifies profiles and their upstream features/minutes, recomputes baseline similarity and rankings, audits cohort/completeness/explanations, and persists an immutable evaluation report. Verification replays the full report and all configuration. Replicates accept integers 2..100, default twenty.

Each replicate retains a player if the first eight SHA-256 hex digits of `evaluation-0.8.0:replicate:player_id`, modulo 100, are below 80. Retention is approximately 80%, not an exact count or stratified sample; all team spells share one player's decision. Queries remain present for similarity while candidate/reference players are thinned. Ranking removes players from both candidate and reference populations and refits percentiles. These are player-cohort perturbations, not match/event resampling, bootstrap confidence intervals, held-out outcome prediction or independent external validation.

Top-five overlap is intersection size divided by baseline top-five count. Unavailable attempts are counted separately and excluded from overlap averages. Summary minimum/maximum are observed ranges; they are not uncertainty intervals. Ranking also reports recovery of retained baseline top-five players: retained baseline members appearing in the new top five divided by retained baseline count. This distinguishes candidate removal from reranking among survivors. Summaries remain separated by position/requirement. AM/CM baseline shortages stay explicit.

Combined checks cover eligible same-role outputs, unique players, similarity self-exclusion, complete feature vectors, ordering, distance/index arithmetic, normalized ranking contributions and candidate filters. Synthetic acceptance adds positive unit/affine transformation invariance, deterministic repeated sampling, honest availability aggregation and rejection of a rehashed false predictive-validation claim. The suite is separate from the deterministic report: no report fabricates a test-run result.

Football sanity cases select the greatest validated-minute available query in each role and expose its closest neighbor and observed metric differences. They verify the implementation's declared scope and explain proxies, not known archetypes or tactical quality. The report labels data-only sanity checks complete, external archetype validation `NOT_PERFORMED`, and predictive validation `NOT_PERFORMED`. Expert/film review and target outcomes are unavailable in this checkpoint. Source restrictions and the limits of one historical league still apply.
