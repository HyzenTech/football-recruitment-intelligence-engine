# Positional profiles - profiles-0.5.0

A profile is one player/team/competition/season record. Transfers remain separate. All feature rows stay visible. Positional exposure is summed from validated Phase 3 intervals, in elapsed seconds including stoppage time, and must equal feature playing seconds. Each source position ID and mapping version must match the explicit eight-group configuration: GK, CB, FB, DM, CM, AM, W, ST.

The largest group becomes the primary group only at a share of at least 60%. Eligibility also requires at least 450 denominator minutes and a full player season with no quarantined appearances. Reasons are recorded individually and may overlap. Nominal minute denominators can be configured, but role shares always use elapsed positional exposure. Unknown minutes never enter the feature input.

Within each role, reference selection keeps one eligible team spell per player: greatest denominator minutes, then ascending team ID. Selection happens before metric completeness filtering. An eligible shorter spell stays a query profile but cannot duplicate its player in the reference population. Different role spells can place a player in different role populations. References include the selected query observation; these are population percentiles, not leave-one-out estimates. No groups are merged to increase sample size.

For counts and sums, compare per-90 values; completion percentage uses its raw percentage. Average shot distance and average action coordinates are descriptive only. Miscontrols/dispossessions use the lower direction; other percentiles describe higher activity. This direction is a convention, not an assertion that more events mean better football.

For a finite query value x and complete reference population of n players:

`percentile = 100 * (count(reference < x) + 0.5 * count(reference == x)) / n`

Lower-direction metrics use `100 - percentile`. Observed exact ties share a percentile. At least ten complete players are required for each reference set. Constant populations suppress percentiles. Missing metrics remain null, never zero. Every comparison exposes peer count, status and a key resolving to explicit player/team reference IDs.

Outfield categories use equal weights and the arithmetic mean of component percentiles:

| Category | Components |
|---|---|
| Passing | attempts, completed passes, completion percentage |
| Progression | progressive passes, progressive carries |
| Carrying | carries, carry displacement, carries into final third |
| Creation | shot assists, shot-linked xG assisted |
| Shooting | nonpenalty xG, shots on target, shots |
| Defensive activity | pressures, interceptions, tackles, recoveries |
| Retention | completion percentage, miscontrols, dispossessions |
| Attacking involvement | final-third actions, box actions |

A category uses one common complete reference population across all its components, then computes each component percentile within that population. This can differ from standalone metric percentiles. Missing components, constant components or fewer than ten complete players suppress the whole category; weights are never redistributed. Artifacts expose weights and component percentiles. Correlated components are not independent evidence, and team possession/context is unadjusted.

Goalkeepers have a distribution activity category using pass attempts and long passes. Passing metrics can have percentiles; other event metrics remain descriptive. Shot stopping is explicitly unsupported by the current feature model. Relative highlights and lower dimensions select the three largest/smallest available metric percentiles; they are neither an overall rating nor claims about absolute strengths and weaknesses.

Builds consume verified canonical-derived artifacts only and retain input hashes, configuration and versions in a manifest. Replay verification checks bytes, positional mapping/exposure, partial-season lineage, reference membership, calculations and report counts. Reproducibility does not establish scouting or predictive accuracy.
