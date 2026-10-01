# Phase 7 checkpoint - recruitment ranking

Completed locally on 2026-09-30. Package 0.7.0; definitions `ranking-0.7.0`. Scope stops before Phase 8 broader evaluation.

## Actual example requirements

Eight illustrative requirements produce six available lists with ten candidates each: 60 returned rows. AM and CM are suppressed rather than merging roles or weakening completeness rules.

| Requirement | Common complete reference players | Status |
|---|---:|---|
| GK distribution | 17 | Available |
| CB defensive activity | 32 | Available |
| FB carrying activity | 26 | Available |
| DM ball-winning activity | 21 | Available |
| CM progression and creation | 3 | Insufficient peers |
| AM creation activity | 1 | Insufficient peers |
| W carrying and shooting | 17 | Available |
| ST shooting activity | 14 | Available |

Reference counts incorporate transfer deduplication and completeness across the requirement's entire feature set. These are criterion-specific activity rankings, not objective ability or transfer availability. [Methodology](RANKING.md) exposes all weight/filter/peer policies.

## Sensitivity

32 scenarios are recorded, including explicitly unavailable AM/CM cases. Across the six available requirements, increasing one active metric weight by 50% retains 80-100% of the baseline top-five players; ordering can still change. Raising the candidate minimum to 600 minutes retains 60% for CB, 80% for FB and ST, and 100% for GK, DM and W. Reference populations remain fixed for these candidate-filter experiments. Results show the importance of declared priorities and minutes rather than validating scouting quality.

## Acceptance and provenance

175 synthetic tests pass. Ranking checks cover exact direction-aware percentiles, normalized weights and contribution sums; one common complete population; ignored zero weights; candidate filters with stable references; transfer selection; deterministic ties/order; huge finite weights; missing/constant components; insufficient peers; invalid/nonfinite weights; unsupported age/value/contract constraints; sensitivity labels; and rehashed artifact tampering. Lint/format checks pass.

Full batch rebuilds produce identical ranking/evaluation artifacts. Replay verification and an independent installed wheel pass. Structural cohort checks confirm unique players per list, requested position and exposure, complete component vectors, stable score ordering, and summed contributions. The named-preset and strict custom-JSON query routes are exercised.

Ranking manifest SHA-256: `b0c3333009bcdbcd446841d6fe63702424baac4c2ed59b7603f248f97f6131d1`, linking profile manifest `1a3841c50f9a32670503871a60c3f2945637acca6e55976f0b53f3340bd59ae0`. Local candidate/component CSVs, full ranking JSON, sensitivity JSON, request example and worked examples are saved beside the repository. Generated player data remain outside Git and the source archive. Source: StatsBomb Open Data, local noncommercial research; provider restrictions remain in force.

Expert/film-based archetype review, predictive validation, availability, valuation, contracts and age evidence are absent. Ranking examples are inspectable demonstrations of the formulas, not actionable transfer recommendations.

## Next phase

Phase 8 extends technical stability and sensitivity evaluation and records the limits of football plausibility review. The minimal interface/API remains Phase 9; no LLM, deployment or publication has been added.
