# Phase 5 checkpoint - positional normalization and profiles

Completed locally on 2026-09-30. Package 0.5.0; profile definitions `profiles-0.5.0`. Scope stops before similarity.

## Actual cohort result

303 player-team-season profiles represent 295 players. All remain visible; 139 profiles meet the configured 450-minute minimum, 60% dominant positional share and full-player-season requirement.

| Position | Eligible profiles |
|---|---:|
| GK | 17 |
| CB | 33 |
| FB | 26 |
| DM | 21 |
| CM | 9 |
| AM | 2 |
| W | 17 |
| ST | 14 |

AM and CM have fewer than ten eligible players, so percentiles/category scores are suppressed. Other comparisons can also fail the ten-complete-player requirement after missingness filtering. No role merging is performed. Reference populations deduplicate transfer spells per player/role.

Exclusion reasons overlap: 85 records below minimum minutes, 57 mixed-position records and 56 partial player seasons. There are 3,672 available metric percentiles and 613 available category scores. Unsupported goalkeeper shot stopping is explicitly labelled. Means and goalkeeper metrics outside passing are descriptive. Scores describe relative activity, not objective ability; there is no overall rating.

## Verification

140 synthetic tests pass, including exact tie/lower-direction percentiles, inclusive thresholds, transfer deduplication, common complete category populations, missing/constant features, role-duration mismatch, goalkeeper scope, partial-season lineage and rehashed profile tampering. Lint and formatting pass. Full offline builds reproduce identical manifests and tables; replay verification passes against verified feature/position inputs. An independently installed wheel produces the same artifacts.

The suite also exposed a Windows ingestion race: resolved paths could retain an extended path prefix while their root did not. Equivalent DOS/UNC representations are now normalized after junction resolution; a regression test reproduces the original failure and verifies that an outside-root path still fails containment. Repeated concurrent transfer ingestions pass after the fix.

Profile manifest SHA-256: `1a3841c50f9a32670503871a60c3f2945637acca6e55976f0b53f3340bd59ae0`. Its source feature manifest is `c0dec39ef24ed670506d01e91ae3ad2932a86d9326d5385c027ba83d608739dc`; positional lineage comes from Phase 3. There are 325 explicit reference sets. [Methodology](PROFILES.md) gives eligibility, formulas, categories, weights and limitations.

Portable local CSV and JSON exports are saved beside this repository. The JSON includes reference membership and component formulas; the CSV exposes metric/category values, peer counts, statuses and role shares. Data source: StatsBomb Open Data; local noncommercial research. Provider restrictions and public attribution/logo obligations remain in force. Generated player data and raw payloads are excluded from Git and the code archive.

## Next phase

Phase 6 builds similarity over common available positional features, with self-exclusion, explicit scaling and distance explanations. Similarity, recruitment rankings, the application and deployment remain unimplemented.
