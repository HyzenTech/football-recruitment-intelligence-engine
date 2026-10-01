# Phase 6 checkpoint - player similarity

Completed locally on 2026-09-30. Package 0.6.0; definitions `similarity-0.6.0`. Scope stops before recruitment ranking.

## Actual cohort result

303 player-team queries are represented. 128 return ten explained neighbors each (1,280 results); 164 are ineligible and 11 have insufficient peers. Available queries: CB 33, FB 26, DM 21, W 17, ST 14, GK 17. AM and CM remain suppressed. Query players are fully excluded, including alternate team spells, and each candidate player occurs once.

Twelve complete event metrics define outfield comparisons; goalkeepers use two distribution metrics. Every result exposes its candidate population, scaling and metric differences. No missing values are invented. [Methodology](SIMILARITY.md) defines feature selection, query eligibility, distance and index.

## Sensitivity results

Baseline: 450 minutes, standard scaling. Overlap measures shared players among the baseline top five, averaged over queries still available in both variants. These are model diagnostics, not accuracy estimates.

| Variant | Evaluated queries | Still available | Mean top-five overlap |
|---|---:|---:|---:|
| Median/IQR scaling | 128 | 128 | 90.31% |
| 300-minute minimum | 128 | 128 | 89.38% |
| 600-minute minimum | 128 | 112 | 86.25% |
| Remove passing family | 111 | 111 | 83.96% |
| Remove carrying family | 111 | 111 | 83.60% |
| Remove shooting family | 111 | 111 | 82.52% |
| Remove defensive family | 111 | 111 | 68.11% |
| Remove attacking zones | 111 | 111 | 84.68% |
| Deterministic reference subsample | 128 | 128 | 77.03% |

The 17 goalkeeper queries are not applicable to the feature-family ablations. Raising the minutes threshold removes 16 baseline queries from availability. Removing defensive activity has the largest observed ablation effect; correlated dimensions and feature-family size can influence this result. This supports exposing model choices rather than treating neighbors as universal matches. The subsample is one declared SHA-256 selection, not repeated sampling or a confidence interval.

## Acceptance

154 synthetic tests pass. New checks cover exact geometry/index/contributions, candidate-only scaling, transfer self-exclusion/deduplication, role restrictions, deterministic input/tie ordering, fixed common complete vectors, missing queries, zero scales, undersized groups, robust quartiles, invalid requests/configuration, sensitivity labels and rehashed artifact tampering. Lint and formatting pass. Full rebuilds reproduce identical query/evaluation artifacts, replay verification passes, and the independent installed wheel reproduces the outputs. Structural cohort checks confirm same-role neighbors, complete vectors, unique players, ordered distances and explained contributions.

Manifest SHA-256: `041e90709a2c909edfc1da6959c8de5b97c6990a4cd6ee1cfbbe416844c7237a`, linking profile manifest `1a3841c50f9a32670503871a60c3f2945637acca6e55976f0b53f3340bd59ae0`. Portable local neighbor/query CSVs, full JSON, evaluation JSON and worked examples are saved beside the repository. Generated player data remain excluded from Git and the source archive. Source: StatsBomb Open Data, local noncommercial research; provider restrictions remain in force.

Worked examples describe observed metric proximity only. No expert/film-based archetype review or predictive scouting validation has been completed. The similarity index is not an ability rating or probability.

## Next phase

Phase 7 implements transparent multi-criteria recruitment ranking over eligible available features. Age, valuation and contracts remain unsupported; no UI, LLM or deployment has been added.
