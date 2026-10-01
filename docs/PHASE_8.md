# Phase 8 checkpoint - combined evaluation and stability

Completed locally on 2026-10-01. Package 0.8.0; definitions `evaluation-0.8.0`. Scope stops before the interface/API.

## Acceptance

186 synthetic tests pass; lint/format and package checks pass. Baseline combined audits cover 1,280 neighbor rows and 60 ranking rows, checking eligibility, roles, deduplication, self-exclusion, completeness, candidate filters, ordering and contribution/index arithmetic. New tests cover deterministic player-level sampling, positive transformation invariance, unavailable attempts, audit failures and a rehashed false predictive-validation claim.

Full evaluations reproduce identical artifacts, including twenty perturbations, and replay verification passes. An independently installed wheel reproduces the same report. Inputs are verified profiles with canonical feature/minute lineage; no raw provider payload is consumed by evaluation.

## Twenty player-cohort perturbations

Similarity keeps each baseline query while thinning references. Ranking thins both candidate and reference players, then refits its benchmark. Approximately 80% of players are retained by a declared salted SHA-256 rule; all spells share a player's retention decision. These are cohort-composition diagnostics, not bootstrap intervals or predictive validation. [Protocol](EVALUATION.md) gives exact formulas.

| Similarity role | Available / attempts | Mean top-five overlap among available attempts |
|---|---:|---:|
| CB | 660 / 660 | 79.55% |
| DM | 420 / 420 | 78.24% |
| FB | 520 / 520 | 76.19% |
| GK | 340 / 340 | 79.06% |
| ST | 202 / 280 | 82.18% |
| W | 340 / 340 | 78.00% |

ST similarity fails the ten-peer requirement in 78 attempts. Its overlap average excludes those failures and must be read with availability. Baseline AM/CM shortages remain unchanged and are not included among available-query experiments.

| Ranking requirement | Available / attempts | Mean top-five overlap | Recovery of retained baseline top-five |
|---|---:|---:|---:|
| CB defensive activity | 20 / 20 | 83.00% | 100.00% |
| DM ball-winning activity | 20 / 20 | 75.00% | 98.00% |
| FB carrying activity | 20 / 20 | 73.00% | 98.75% |
| GK distribution | 20 / 20 | 73.00% | 94.00% |
| ST shooting activity | 18 / 20 | 84.44% | 97.78% |
| W carrying and shooting | 20 / 20 | 81.00% | 100.00% |

AM and CM ranking requirements remain unavailable in all twenty attempts each. ST ranking becomes unavailable twice. Recovery conditions on baseline players retained by sampling and available variant lists; it is not overall accuracy. Cohort removal and benchmark changes affect results, so scores should remain accompanied by peer size, weights and explanations.

## Football review boundary

Six data-grounded cases expose greatest-minute queries by role, closest neighbors and metric differences. Same-role/metric/explanation checks pass. Goalkeepers remain distribution-only; shooting and defensive activity remain event proxies. No expert/film-based archetype validation, external outcome study or predictive accuracy claim is made. The report records those validation types as `NOT_PERFORMED` rather than fabricating a pass.

Evaluation manifest SHA-256: `80ab3dfe8e9d1286c85c889d1553c824107171c18e3f89b2aedcd8adc83b5284`, linking profile manifest `1a3841c50f9a32670503871a60c3f2945637acca6e55976f0b53f3340bd59ae0`. Portable local report/summary/record CSVs are saved beside the repository. Player-derived outputs and source payloads remain excluded from Git/source archives. Source: StatsBomb Open Data, local noncommercial research.

## Next phase

Phase 9 adds a minimal interface/API over verified outputs, with explicit unsupported controls and no fabricated fallback statistics. Publication, deployment and LLM features remain outside this checkpoint.
