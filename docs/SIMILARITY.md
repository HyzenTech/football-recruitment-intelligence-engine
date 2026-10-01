# Player similarity - similarity-0.6.0

Implemented offline over verified Phase 5 profiles. The public Python function is `find_similar_players(profiles, player_id, team_id, settings, position_group=None, top_k=None)`; optional arguments are keyword-only. Names are display labels; IDs and team spells resolve identity. The CLI loads and verifies the input before calling this function.

## Population and completeness

Queries and candidates must meet the profile policy: 450 minutes, 60% dominant positional share, no partial player season. Compare only within the same broad positional group and cohort. An explicit position override must match the validated group. Exclude every team spell of the query player. Select one candidate spell per player by greatest denominator minutes, then ascending team ID, before completeness filtering. Transfers cannot duplicate neighbors.

The candidate must have a complete value for every configured feature; missing values are never filled with zero. Every candidate uses the same feature vector. An incomplete query produces no neighbors. At least ten complete candidates must remain after self-exclusion. Undersized groups return a labelled empty result; no AM/CM merging occurs. `top_k` accepts 1..50, default ten. A request above the candidate count returns fewer neighbors with an explicit warning.

`config/similarity.toml` declares the fixed outfield feature vector, all per-90:

- Passing volume: pass attempts, long passes.
- Carrying: carries, carry displacement.
- Shooting: shots, nonpenalty xG.
- Defensive activity: pressures, interceptions, tackles, recoveries.
- Attacking zones: final-third actions, box actions.

These twelve metrics are complete for all current eligible profiles. Completion, progressive passing and creation are deliberately absent from this initial model because source outcome/link completeness limits those metrics. The fixed selection is a versioned modeling decision, not a per-query fallback. Goalkeepers use pass attempts and long passes only: distribution similarity, without any shot-stopping claim. Counts describe activity and lack team-possession/context adjustment.

## Scaling, distance and index

Fit scaling on the complete candidate population after query-player exclusion. Standard scaling uses population mean and population standard deviation (divide variance by n). A vector coordinate is `(value - mean)/standard_deviation`. Euclidean distance is `sqrt(sum(((query_value - candidate_value)/standard_deviation)^2))`, with equal weight on each active standardized coordinate.

A zero-scale feature is omitted for the entire query population, with its scaler status and a warning. If all features have zero scale, return `NO_VARIABLE_FEATURES`. The same rule applies to robust scaling, which uses the median and interquartile range; quartiles use linear interpolation at `(n-1)*fraction`. A zero IQR can occur in a nonconstant sparse feature and is still explicitly omitted. No hidden missingness reweighting occurs.

The displayed similarity index is `100/(1+distance)`. It is a monotonic convenience index, not a probability or ability rating. Exact identical active vectors give distance zero and index 100. Distance ordering uses full precision; ties break by player ID then team ID. Query-specific scalers mean distances need not be symmetric. Indices should not be compared across roles, feature sets, queries or scaling scenarios.

Each result exposes reference IDs, peer count, selected/active features, means/scales and exclusions. Each neighbor exposes all raw differences, standardized differences, squared contributions and contribution shares. Three smallest absolute standardized differences explain key similarities; three largest explain key differences. At zero distance, contribution shares are zero because there is no discrepancy to apportion. Similarity does not establish shared absolute strengths, tactical fit or recruitment desirability.

## Reproducibility and sensitivity

`build-similarity` saves immutable query and evaluation artifacts with source profile hash/configuration. `verify-similarity` replays both artifacts from verified profiles, including report counts and settings. `find-similar` queries directly from a profile manifest.

The checkpoint compares robust scaling, 300/600-minute thresholds, five feature-family ablations and a deterministic reference subsample. Top-five overlap is intersection size divided by the baseline top-five count. Results are averaged only over queries still available in both scenarios; unavailable counts are reported separately. Threshold experiments reevaluate minute eligibility while retaining primary position and partial-season exclusions. Ablations remove entire declared families; GK ablations that would remove all features or change nothing are marked not applicable. Subsampling retains players whose first eight SHA-256 hex digits modulo five are nonzero; it is one declared subsample, not a statistical confidence interval. All scalers are refit on each scenario's candidates.

These checks diagnose modeling sensitivity. Technical consistency checks are separate from football plausibility and predictive validation; no expert/film-based archetype review has been completed. [Phase 6 results](PHASE_6.md) record actual counts and overlaps. Repeated cohort diagnostics are recorded in [Phase 8](PHASE_8.md); external archetype and predictive validation remain unperformed.
