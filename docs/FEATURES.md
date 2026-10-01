# Feature definitions - implemented Phase 4

Version `features-0.4.0` implements 41 metrics. [Phase 4 evidence](PHASE_4.md) records the full-cohort build. The [StatsBomb event specification](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/Open%20Data%20Events%20v4.0.0.pdf) supplies provider field semantics; thresholds and inclusion rules below are explicit project definitions.

## Eligibility and exposure

Read verified canonical events and Phase 3 appearances/presence. Include only player-attributed, non-administrative period 1-4 events for a VALIDATED appearance of the same team, within its observed presence intervals. Quarantined appearances, roster-only players, administrative records and shootouts contribute to neither event numerators nor playing-time denominators. Unreviewed event schema flags fail the build. Unknown pass outcomes are retained as declared missing opportunities.

A player-match row exists for every validated appearance, even with no observed events. A player-team-season row aggregates those rows by player, team, competition and season. Transfers remain separate team rows. Exposure includes all validated seconds, not only event-active seconds. Seasons with excluded appearances or partial source coverage are explicitly marked partial. There is no fabricated row for a player with only quarantined/unused records.

## Missingness and rates

Each metric retains numerator, opportunity sample count and missing opportunity count. Add sufficient statistics before deriving season values. A count/sum is unavailable if any contributing opportunity is missing; its observed partial numerator remains labelled separately. Coverage is `(samples-missing)/samples`, or null for no opportunities. A mean/percentage is null for zero samples. Zero count with no opportunities is a valid observed zero.

`per90 = 90 * total / denominator_minutes`, for counts/sums only. Means and percentages have no per-90. The denominator follows `cohorts.minutes_convention`: default elapsed seconds / 60 including added time, or the separately labelled nominal-window minutes. Nonpositive denominator returns null. Never average match per-90s. The provisional 450-minute setting produces a flag, not a row deletion or a scouting eligibility claim.

## Implemented metrics

| Group | Metrics and exact rules |
|---|---|
| Passing | `passes_attempted`: all eligible Pass events, including unknown outcomes. `passes_completed`: complete canonical outcomes. `pass_completion_pct`: 100 times completed / attempts; any unknown outcome makes the full rate null. `forward_passes`: end_x greater than start_x for all attempts. `switches`, `crosses`: canonical true flags. `long_passes`: provider pass length >= configured 30 yards, for all attempts. |
| Passing entries | `passes_into_final_third`: completed pass with start_x < 80 <= end_x. `passes_into_box`: completed pass from outside to inside the configured box. Unknown outcomes suppress these full counts; known unsuccessful passes contribute zero. |
| Progression | `progressive_passes`, `progressive_carries`: the project proxy below, with explicit open-play filtering. |
| Carries | `carries`: Carry events, separate from dribbles. `carry_displacement`: summed Euclidean endpoint displacement. `carries_into_final_third`, `carries_into_box`: same entry boundaries as passes, without a pass-outcome requirement. |
| Creation | `shot_assists`: unique validated pass-to-shot links. `shot_linked_xg_assisted`: linked provider shot xG sum. These include goals and penalties and are not an official xA model. |
| Shooting | `shots`: Shot events, excluding own-goal event types and shootouts. `goals`: Shot outcome Goal. `shots_on_target`: Goal, Saved, Saved to Post (the observed source spelling; Saved To Post is also accepted). Post, Blocked and Saved Off Target are excluded. Unreviewed outcomes suppress outcome-dependent counts. |
| Shooting context | `xg`: all eligible shot xG. `penalty_shots`, `nonpenalty_shots`, `nonpenalty_xg`: Shot type Penalty vs other known types. Unknown type suppresses dependent metrics. `average_shot_distance`: mean Euclidean start-to-goal-centre grid distance. `shots_inside_box`: shot starts inside the box. |
| Defense | `pressures`: Pressure events; `counterpressures`: Pressure events with counterpress true. `interceptions`: Interception events, not inferred passing interceptions. `recovery_attempts`: Ball Recovery events; `recoveries`: those without canonical recovery_failure. `tackles`: Duel subtype Tackle, not all duels. `blocks`, `clearances`: corresponding event counts. |
| Possession | `miscontrols`, `dispossessions`: corresponding event counts. `event_involvements`: every eligible player-attributed non-administrative event, not a count of unique physical touches. |
| Spatial | `average_action_x`, `average_action_y`: means over located eligible events. `final_third_actions`, `box_actions`: counts of located starts in those zones. Unlocated events are outside this spatial sample, with sample counts visible. |

Missing coordinates suppress dependent endpoint/distance metrics. Missing canonical flags suppress their flag-dependent metrics, rather than silently becoming false. The pinned adapter already maps schema-defined absent boolean flags to false where appropriate.

## Progression and geometry

Convert normalized canonical coordinates back to configured provider units: x times 120, y times 80. Coordinate-derived displacements are grid units, not metres or tracking distances. The separate canonical pass-length field is yards in the pinned StatsBomb specification; its long-pass threshold is explicitly labelled in yards. Do not flip second-half coordinates again.

`D(x,y) = sqrt((120-x)^2 + (40-y)^2)`. A progressive action requires `D_start > 0`, forward x movement when configured, and `D_start-D_end >= max(10, 0.25*D_start)`. Pass completion is required by default. Threshold equality is included.

Default progression open-play patterns are exactly Regular Play and From Counter. This deliberately narrow project convention excludes patterns From Corner, From Free Kick, From Throw In, From Goal Kick, From Keeper and Other. Explicit pass restart types Corner, Free Kick, Goal Kick, Kick Off and Throw-in remain excluded even with an allowed pattern. Missing play pattern suppresses the dependent metric; known excluded patterns contribute zero. Settings are persisted in the feature manifest.

Final-third boundary is x=80. Box is x>=102 and 18<=y<=62. Entries require outside-to-inside movement; starting inside is not an entry. These zones are configurable.

## Shot-link validation

Target must exist, be a Shot, have the same team and period, occur no earlier than the pass, and belong to a validated appearance/presence. Its optional key_pass_id must agree. Each shot can contribute only once per match. Invalid, ineligible or duplicate links create explicit missing opportunities for both creation metrics and a report issue; they do not become zero chances. Missing linked xG suppresses xG-assisted while leaving a valid assist count intact.

## Reproducibility and limits

`fre build-features --manifest <minutes manifest>` verifies upstream sources, produces two immutable JSONL tables and a content-addressed feature manifest. `fre verify-features --manifest <feature manifest>` checks hashes, validated exposure census, team-season aggregation, missingness, rates and threshold flags. Exact synthetic tests validate formulas separately.

No percentiles, role dominance, composite scores, similarity or ranking are produced in Phase 4. Pressure counts are activity, not effectiveness. Spatial action means are observed usage, not tracking positions. Partial seasons and missing metrics require declared eligibility policies in later comparison stages.
