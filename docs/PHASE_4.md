# Phase 4 checkpoint - feature engineering

Completed locally on 2026-09-30. Package 0.4.0; feature definitions `features-0.4.0`. Scope stops before positional normalization/profiles.

## Actual full-cohort result

| Result | Count |
|---|---:|
| Matches checked | 132 |
| Eligible player-match rows | 3,917 |
| Player-team-season rows | 303 |
| Distinct players with validated exposure | 295 |
| Implemented metrics | 41 |
| Included non-administrative events | 482,977 |
| Administrative events excluded | 4,797 |
| Events without validated appearances excluded | 7,415 |
| Quarantined appearances excluded | 67 |
| Partial player-team seasons flagged | 56 |

The event census sums to all 495,189 ingested records. No quarantined appearance contributes to numerators or denominators. Transfers remain separate team-season records. All validated appearances produce rows, including short appearances; the minimum-minute flag uses the provisional 450-minute setting.

Unknown pass outcomes suppress full completion totals/rates for 186 player-team seasons while attempts, observed partial numerators and coverage remain explicit. Fifteen invalid/ineligible shot links affect creation completeness in 14 player-team seasons. Known source shot outcomes, including Saved to Post, are classified explicitly. These are data limitations, not manufactured zeros.

## Acceptance

130 synthetic tests pass. Tests cover exact progression/zone boundaries, configuration, set-piece exclusion, incomplete/unknown outcomes, missing locations/xG, count vs percentage zero denominators, carry displacement, unique/eligible shot links, shot outcomes, aggregation before rates, transfers, quarantine, input corruption and tampered derived rates. Lint and formatting pass.

Full offline reruns produce identical feature manifests and tables. Independent feature verification passes. The source distribution and installed wheel are checked; no provider payloads or generated player tables enter Git or the source archive.

The feature manifest SHA-256 is `c0dec39ef24ed670506d01e91ae3ad2932a86d9326d5385c027ba83d608739dc`. It links Phase 3 manifest `b7fa8ddce9427bff049eb6594db825621cc87a3279db3fc0d7b1e5111f91245b` and the pinned Phase 2 source manifest. Generated tables live under ignored `data/processed/statsbomb/<revision>/37-281/features-0.4.0/`. [Metric definitions](FEATURES.md) specify every formula and missingness convention.

A local portable CSV is also saved beside the source project. Blank values mean unavailable; per-90 is omitted for means/percentages. Source: StatsBomb Open Data, noncommercial research. This local artifact is not a public release; provider attribution/logo and licensing obligations still apply to any later publication.

## Next phase

Phase 5 derives positional exposure/peer groups and interpretable profiles. It must expose partial-season and metric-coverage eligibility, suppress undersized peer groups, and avoid comparing unavailable features as zeros. No similarity engine, recruitment ranking or UI is implemented yet.
