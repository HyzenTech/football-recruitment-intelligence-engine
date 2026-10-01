# Phase 3 checkpoint â€” validation and minutes

Completed locally on 2026-09-30. Package 0.3.0, minutes method `presence-0.3.0`. Scope stops before feature engineering.

## Full-cohort results

All 132 ingested WSL matches were checked offline against the pinned Phase 2 manifest `380994c3de5306aad9fd7f0e09086264a26398d7072e62015df6d425bd94c935`.

| Roster disposition | Count |
|---|---:|
| Validated appearances | 3,917 |
| Appearances requiring review | 67 |
| Unused roster entries | 1,118 |
| Total accounted roster entries | 5,102 |

Review records occur in 21 matches. One whole match, 3913096, is quarantined because a ball action occurs after the recorded first-period end; its 27 appearances expose no usable minutes. Other errors are localized to affected appearances. Match 3913150's previously observed overlapping positions are detected and excluded for the affected appearance.

There are 35 reported position-overlap instances, 34 position/presence disagreements, 18 invalid source position observations, 61 zero-duration warnings, and two source card clocks independently resolved from matching canonical events. These issue counts overlap; they are not distinct players or appearances. The 427 unclassified pass outcomes remain feature warnings and are not treated as successful/unsuccessful passes.

## Implemented

Verified offline canonical input -> event-state reconstruction -> independent lineup-position cross-check -> quality-gated appearances, periods, presence and position intervals -> immutable report and processed manifest. No features or per-90 analytics are produced. Elapsed time includes added time and subtracts recorded temporary absences; nominal-window minutes are labelled separately. See [methodology](MINUTES.md).

Processed output goes beneath ignored `data/processed/statsbomb/<revision>/37-281/presence-0.3.0/`. Detailed per-match reports go beneath ignored `outputs/validation/`. The command summary records exact report/manifest paths and hashes. Neither raw payloads nor derived player records are included in the code archive.

## Acceptance

107 synthetic tests pass, including exact clock arithmetic, added time, halftime substitutions, temporary exits/returns, substitution while absent, permanent exits, both dismissal types, bench dismissals, extra time/shootout exclusion, overlap/gap/reversed evidence, unreliable coverage, unknown event types, corrupt input/output and minute-total mismatches. Lint/format checks pass.

Full offline runs are deterministic. Independent `fre verify-minutes` verifies processed artifacts and interval invariants. Package distributions and an installed wheel are checked outside the checkout. Passing checks certify the declared artifact/method boundary; excluded records remain unresolved.

The processed manifest SHA-256 is `b7fa8ddce9427bff049eb6594db825621cc87a3279db3fc0d7b1e5111f91245b`. Verification covers 262 usable period records, 6,904 presence intervals and 8,259 position intervals. The two periods of the quarantined match are excluded.

## Next phase

Phase 4 builds interpretable player-match and player-season features from eligible canonical events and validated appearances. It must keep excluded appearance events out of both numerators and denominators and define handling of unclassified pass outcomes before computing completion rates. Role/peer normalization, profiles, similarity, ranking and UI remain deferred.
