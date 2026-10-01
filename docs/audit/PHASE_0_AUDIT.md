# Football Recruitment Intelligence Engine — Phase 0

Audited 30 September 2026, Asia/Jakarta. Status: **Phase 0 complete; Phase 1 not started.**

## Recommendation and evidence boundary

Proceed with a **noncommercial, reproducible research/portfolio engine using FA Women's Super League 2023/24**, StatsBomb competition `37`, season `281`. Keep football-data.org optional for context. Exclude age constraints, market values, transfer availability, LLMs and tracking-dependent claims from V1.

This is a dataset recommendation, not a claim that the resulting system is ready to make real recruitment decisions. The cohort is historical, role groups differ in size, and the minutes audit found an overlapping interval requiring explicit handling.

Both supplied requests are identical. This workspace had no application source to inspect. Only research notes, bounded data inspection and audit scripts were created; no application, project scaffold, provider implementation, dependency environment or Git repository was created. Prior ScoutLens work is separate; no existing product was rewritten or treated as proof of this engine's feasibility.

The official `statsbomb/open-data` repository currently redirects to `hudl/open-data`. All machine inspections use commit **`4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`**, rather than a moving branch. [Official repository](https://github.com/hudl/open-data)

Evidence scope:

- Parsed the competition catalog and **all 80 competition-season match lists**; checked file presence against a non-truncated Git tree.
- Counted **24 competition IDs and 3,961 unique listed matches**. Every listed match has an event and lineup file at this snapshot. Presence is not evidence that every file is internally complete.
- Parsed all **132 WSL lineup files** and match metadata.
- Inspected **13 event files / 48,220 events**: eight WSL matches spread across the season, three Liga F 2023/24 matches, and two Premier League 2015/16 matches. The WSL subset contains **30,215 events**. This is a deterministic diagnostic sample, not a random estimate of season-wide defect rates.
- Read the official event, lineup, match and consolidated specifications. Older documentation is incomplete relative to current payloads; actual lineup files contain `positions` and `cards` not listed in the 2019 lineup PDF.
- Checked football-data.org's official pricing, coverage, references and terms. **No authenticated football-data.org API payload was tested.**

The detailed cross-competition inventory is retained privately. See [machine-readable audit evidence](AUDIT_EVIDENCE.json), and [source policies](SOURCE_POLICY_AUDIT.md). Evidence includes URLs, hashes, file sizes and sample IDs; raw provider payloads remain local scratch material.

## A. Source assessment

| Source | Exact V1 role | Available data and important fields | Access and coverage | Suitability and boundary |
|---|---|---|---|---|
| StatsBomb Open Data | Primary event analytics and appearance source | Competition/season IDs; match date, teams, score and data versions; player identity/nationality; lineup position intervals/cards; event UUID, order, period, timestamp, possession, actor/team, coordinates and event-specific objects | Public JSON from official GitHub, no API token required for raw file reads. Coverage is a curated collection, not all leagues or all seasons | Sufficient for transparent event-derived profiles, similarity and ranking within a selected cohort. No general DOB, contracts, valuations or continuous tracking |
| StatsBomb 360 | Future optional contextual extension | Event-linked visible-player locations and visible area | Only selected matches; separate files | Not needed for V1. File presence does not imply all-event/full-pitch observation; cannot substitute for tracking |
| football-data.org | Optional competitions/fixtures/results/standings context | Competition/code/season; team IDs/names; match date/status/score; standings | HTTPS v4 API. Free plan advertises 12 competitions, delayed scores/schedules, fixtures/tables and 10 calls/minute | Adds limited value to the chosen WSL cohort, which is outside its published free list. Do not make it a dependency of the analytics pipeline |

The StatsBomb README defines the JSON directory layout and public-research purpose. [README](https://raw.githubusercontent.com/hudl/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/README.md)

The football-data.org free competition list is: Champions League (`CL`), Primeira Liga (`PPL`), Premier League (`PL`), Eredivisie (`DED`), Bundesliga (`BL1`), Ligue 1 (`FL1`), Serie A (`SA`), La Liga (`PD`), Championship (`ELC`), Brazilian Série A (`BSA`), World Cup (`WC`), European Championship (`EC`). Historic-season access is not established by this list. [Coverage](https://www.football-data.org/coverage), [Pricing](https://www.football-data.org/pricing)

Relevant documented routes are `/competitions`, `/competitions/{code}`, `/competitions/{code}/matches`, `/competitions/{code}/standings`, `/competitions/{code}/teams`, `/teams/{id}`, `/teams/{id}/matches`, `/matches/{id}`, `/competitions/{code}/scorers`, `/persons/{id}` and `/persons/{id}/matches`, under `https://api.football-data.org/v4`. Registration supplies `X-Auth-Token`. Anonymous access is documented at 100 requests/24 hours, limited to area and competition lists. Shared throttling, caching and reset-aware retries are required for later integration. [Routes](https://www.football-data.org/documentation/quickstart), [Policies](https://docs.football-data.org/general/v4/policies.html)

**Do not mistake documented payload fields for free-plan entitlements.** Squads, lineups/substitutions and scorers appear in the paid Deep Data feature list. Person birth dates, contracts and market values in schema examples do not establish current values, coverage or free access. A token-based read test would be needed before using any of these. There is no evidence here of StatsBomb-like pass/carry/pressure coordinates from this service. [Pricing](https://www.football-data.org/pricing), [Person reference](https://docs.football-data.org/general/v4/person.html), [Team reference](https://docs.football-data.org/general/v4/team.html)

### Licensing and portfolio publication

StatsBomb's Public Data User Agreement is a bespoke data agreement, **not a permissive software licence**. It permits research/analysis and public conclusions, requires its logo on published analysis, restricts redistribution/reproduction/provision of the data, and prohibits commercial exploitation of both the data and derived analysis. The agreement also asks users to supply name/email through the resource centre; no registration was performed on your behalf. [Official pinned agreement](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf)

Recommended publication boundary: publish code, formulas, synthetic tests, provenance manifests and attributed noncommercial analytical demonstrations. Have users fetch source data from the official provider. Keep raw JSON, cached payloads and database/event-row exports out of public Git and app downloads. Preserve immutable source bytes locally. Provider permission is needed before treating this as a commercial club service or redistributing data. This is a design interpretation of the reviewed agreement; the wording about modifying data must not be represented as permission to republish transformed event tables.

football-data.org requires visible provider attribution and forbids publishing developer credentials. Team crests/photos have separate rights; access to a URL does not grant reuse rights. Its reviewed terms do not establish a broad raw-data redistribution licence. [Registration terms](https://www.football-data.org/client/register)

No additional source is necessary to establish V1 feasibility. No scraping is proposed.

## B. Inventory and candidate comparison

The accompanying inventory lists **every competition and available season**, with exact counts and pinned per-row sources. A sample of useful candidates and coverage traps follows; counts are observed match-list lengths, not inferred from league names.

| Competition / season | IDs | Matches | Teams represented | 360 files | Assessment |
|---|---|---:|---:|---:|---|
| WSL 2023/24 | 37 / 281 | 132 | 12 | 0 | Recommended: recent, balanced repeated club observations, manageable scale |
| Liga F 2023/24 | 182 / 281 | 240 | 16 | 0 | Strong alternative: larger peer pool; three sampled event files support core metrics, full lineup audit not performed |
| Frauen Bundesliga 2023/24 | 135 / 281 | 132 | 12 | 0 | Plausible alternative; catalog/file presence checked, content not sampled |
| NWSL 2023 | 49 / 107 | 137 | 12 | 0 | Repeated club data, but separate competition-stage analysis needed |
| Indian Super League 2021/22 | 1238 / 108 | 115 | 11 | 0 | Plausible men's alternative, including stage/match-format checks |
| Premier League 2015/16 | 2 / 27 | 380 | 20 | 0 | Broad men's alternative; two sampled files include pressures/carries, but older recruitment context |
| La Liga 2015/16 | 11 / 27 | 380 | 20 | 0 | Broad older men's season; full content validation still required |
| Serie A 2015/16 | 12 / 27 | 380 | 20 | 0 | Broad older men's season; full content validation still required |
| Ligue 1 2015/16 | 7 / 27 | 377 | 20 | 0 | Near-season coverage; investigate missing fixtures before calling complete |
| Bundesliga 2023/24 | 9 / 281 | 34 | 18 | 34 | Selective sample; opponent representation does not imply equal coverage |
| La Liga 2020/21 | 11 / 90 | 35 | 19 | 35 | Selective sample; unsuitable default for league-wide rankings |
| Ligue 1 2022/23 | 7 / 235 | 32 | 20 | 32 | Selective sample; same exposure problem |
| World Cup 2022 | 43 / 106 | 64 | 32 | 64 | Useful tournament/360 demonstration; unequal matches and low player minutes |
| Euro 2024 | 55 / 282 | 51 | 24 | 51 | Tournament alternative with small/unequal player exposure |
| Women's Euro 2025 | 53 / 315 | 31 | 16 | 31 | More recent, but smaller tournament cohort |

The detailed pinned catalog audit is retained privately. Most historical Champions League seasons contain only one match. WSL 2020/21 lists 131, 2019/20 lists 87, and 2018/19 lists 107; do not pool these as equivalent complete seasons.

## C. Event schema and metric support

The event schema has common fields plus type-specific objects. Common fields include `id`, `index`, `period`, `timestamp`, `minute`, `second`, `type`, `possession`, `possession_team`, `play_pattern`, `team`, optional `player`, optional `position`, optional `location`, `duration`, `related_events`, and conditional booleans such as `under_pressure`, `counterpress` and `off_camera`. Absence of an actor or location on administrative events is expected, not a missing-value defect. [Event specification](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/Open%20Data%20Events%20v4.0.0.pdf)

Across eight WSL files, 31 event types were observed: `50/50`, `Bad Behaviour`, `Ball Receipt*`, `Ball Recovery`, `Block`, `Carry`, `Clearance`, `Dispossessed`, `Dribble`, `Dribbled Past`, `Duel`, `Error`, `Foul Committed`, `Foul Won`, `Goal Keeper`, `Half End`, `Half Start`, `Injury Stoppage`, `Interception`, `Miscontrol`, `Offside`, `Pass`, `Player Off`, `Player On`, `Pressure`, `Referee Ball-Drop`, `Shield`, `Shot`, `Starting XI`, `Substitution`, `Tactical Shift`. The official vocabulary also includes types not observed in this sample, including own-goal events. Use versioned numeric types and a registry; do not build an exhaustive enum from the sample alone.

Provider-specific details to preserve:

- `pass`: end location, recipient, outcome, length/angle, body part, height, type, assist flags and `assisted_shot_id` when applicable. An absent pass outcome denotes completion in this schema; do not globally treat absent outcomes as success for every event type.
- `carry`: end location. Carries are distinct from successful dribbles.
- `shot`: `statsbomb_xg`, outcome, body part, type, technique, `key_pass_id` and optional freeze frame. Shot endpoints can include a third height coordinate.
- `duel`: type and outcome; a tackle is a subtype, not every duel.
- `ball_recovery`: failure flag; a recovery event is not automatically successful.
- `tactics.lineup`: starting and tactical positions; `substitution.replacement` identifies the entering player. Cards occur in both foul and bad-behaviour event payloads.

**Coordinates:** the official pitch diagram uses a 120-by-80 grid, centre `(60,40)`, goal centres `(0,40)` and `(120,40)`, and attacking penalty box boundary `x=102`, `y=18..62`. These are provider grid coordinates, not measured player travel in metres. Keep an explicit team-relative attack direction and coordinate convention in canonical data; do not mirror a second half automatically. Opponent pressure locations require appropriate transformation before joining attacking spatial contexts. [Consolidated specification, Appendix 2](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf)

The sampled WSL events had zero duplicate event UUIDs, malformed timestamp strings, out-of-range start/pass/carry coordinates, missing pass/carry endpoints, missing shot xG values, or broken assisted-shot references. There were 211 shots and 146 valid assisted-shot links. All 13 sampled event files had contiguous event ordering and no actor/team/roster membership mismatch. These findings do not cover all season events, shot endpoint validation or all cross-event relations. [Audit evidence](AUDIT_EVIDENCE.json)

## D. Starts, substitutions, positions and playing time

The full WSL lineup audit found **336 distinct roster player IDs**, 5,102 team-sheet player records, 3,984 records with position intervals and 1,118 without intervals. Team-sheet membership must not be counted as an appearance. Every roster record has identity, nickname, shirt number, country, cards and positions; **none has a birth-date field**.

Position intervals contain `position_id`, `position`, `from`, `to`, `from_period`, `to_period`, `start_reason`, `end_reason`. Reasons include Starting XI, Tactical Shift, substitution on/off, temporary Player Off/On, off-camera variants, permanent exits, red cards and second yellow. There are 2,904 Starting XI segments, consistent with 132 × 22 starters. This is supporting evidence, not a replacement for a per-team starter identity check. [Pinned example lineup](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/lineups/3912592.json)

Recommended production calculation, to implement and test in Phase 3:

1. Build ordered period bounds from `Half Start`/`Half End`; team-labelled duplicate boundary events must collapse to one period boundary. Reject or flag early video end, suspension and inconsistent boundaries.
2. Treat event `timestamp` as period elapsed time. Preserve period separately: `minute` resets to nominal 45/90/105 starts and must not be used as a continuous elapsed clock across stoppage and half-time.
3. Convert lineup `MM:SS` clock values using their stated period. For regulation period two, subtract 45 minutes to get period elapsed seconds. A cross-period interval must split at boundaries, preserving first-half added time and excluding half-time.
4. Resolve `to=null` only when an explicit final-whistle reason and verified final playable boundary support it. Do not assume every null means 90 minutes.
5. Reconcile lineups with Starting XI, Substitution, Player Off/On, tactical changes and dismissal events. Retain role intervals separately from on-pitch presence. Inspect cards by semantic type; different event objects use different numeric card IDs.
6. Check intervals for overlap and invalid ordering. Union intervals prevents mathematical double counting, but unresolved source contradictions must remain flagged and excluded from default comparisons. Never silently repair contradictory role labels.
7. Sum playable interval lengths for `playing_seconds`. Also derive separately labelled nominal-regulation minutes for conventional reporting. Extra-time periods contribute when present; shootouts do not. A regulation appearance exceeding 90 elapsed minutes can be valid because of added time.
8. Per-90 is `90 * total / minutes`, with the declared denominator convention. Zero/unknown minutes produce null plus a quality flag, not infinity or a fabricated zero rate. Apply the same convention to eligibility and roles.

Concrete check: match `3912592` ends period one at `00:46:01.003` and period two at `00:54:49.065`. Its elapsed match duration is **100.8345 minutes**, excluding half-time. An entering player at clock `70:16` in period two starts at elapsed `25:16` in that period. Assuming 90 minutes or simply taking the last global clock produces a different answer. [Pinned event file](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/events/3912592.json)

**Observed defect:** match `3913150` has one player's overlapping first-half lineup intervals, approximately **60.736 seconds** under sampled period bounds. A naive sum exceeds the match duration. Production validation must surface this and reconcile against Player Off/On events or exclude the ambiguous appearance. Feasibility is supported; reliable season-wide minutes are **not yet certified**. [Pinned lineup](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/lineups/3913150.json)

Preliminary lineup-only nominal-minute diagnostics found 290 players with positive clipped regulation time. At 450 minutes, approximately 210 qualify; at 900, approximately 136. These are provisional, using interval sums and clipping each half to 45 minutes; added-time-only appearances and overlaps mean these are not final production eligibility counts.

| Primary broad group | Approx. peers at 450 nominal minutes | At 900 |
|---|---:|---:|
| Goalkeeper | 20 | 11 |
| Centre-back | 43 | 33 |
| Full-back / wing-back | 34 | 25 |
| Defensive midfield | 31 | 20 |
| Central midfield | 15 | 11 |
| Attacking midfield | 5 | 1 |
| Wide midfield / winger | 36 | 20 |
| Striker / secondary striker | 26 | 15 |

Mapping is by position ID, weighted by nominal interval duration; this is a broad comparison convention, not inferred tactical role. Right/left midfield maps to wide midfield; attacking midfield stays separate; secondary striker maps to striker with a retained subtype. Choose dominant role by validated duration, deterministic tie-breaking and a configurable mixed-role flag. Goalkeeper similarity/ranking requires a separate suitable feature set.

**Proposed default:** 450 minutes, with a minimum peer group of ten; report cohort size and suppress robust-percentile/ranking claims below that. Do not silently combine AM and CM or promise ten neighbors when only four exist. Re-run eligibility with validated minutes before locking defaults.

## E. Recommended cohort

WSL 2023/24 has a balanced catalog: 12 teams, 22 listed fixtures per team, 132 unique matches spanning **1 October 2023 to 18 May 2024**. All 66 distinct opponent pairs appear exactly twice. All metadata rows declare data version `1.1.0`, shot fidelity `2`, xy fidelity `2`. All matches have event and lineup files. The season offers repeated player/team observations with observed passing, carry, shooting, defensive and pressure fields, without requiring 360.

It is small enough for rapid reproducible iteration, recent enough to avoid making a decade-old cohort the default, and supports the eight broad position groups. Balanced team exposure is a stronger basis for within-cohort comparisons than selective superstar/opponent match collections. [Pinned WSL match list](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/matches/37/281.json)

Limits: one historical women's league, no 360, no age/valuation/contract eligibility, sparse AM peers and unvalidated full-season events. Results cannot be extrapolated to current men's recruitment or cross-league strength. If a men's-only cohort is a requirement, choose Premier League 2015/16 as the broad sampled alternative and explicitly accept its age; if larger modern peer groups matter more than iteration cost, consider Liga F 2023/24 after a full lineup audit.

## F. Feature feasibility matrix

Availability means official schema plus bounded observations unless otherwise stated. Confidence describes computability under the definition, not ability to predict football quality. Derived definitions below are proposals to approve/version before implementation.

| Feature | Raw fields required | Available? | Derivation | Confidence | Notes |
|---|---|---|---|---|---|
| Pass attempts/completions | type, pass.outcome | Yes | Count Pass; completion where outcome absent under verified schema | High | Separate open-play and set-piece subsets |
| Completion % | attempts/completions | Derived | 100 × completed / attempted; null for zero attempts | High | Difficulty/context not adjusted |
| Forward passes | location, pass.end_location | Yes | End x > start x in actor attack frame | High | Grid orientation must be explicit |
| Progressive passes | start/end, completion | Derived | Completed forward pass satisfying proposed goal-distance rule below | Medium | Custom proxy; no universal official progressive flag established |
| Progressive carries | location, carry.end_location | Derived | Carry satisfying same proposed rule | Medium | Carry segmentation can affect counts |
| Final-third entries | start/end, completion | Derived | Start x < 80 and end x ≥ 80; count completed passes/carries separately | High | Distinguish entries from actions occurring inside zone |
| Penalty-area entries | start/end, completion | Derived | Start outside, end inside x ≥ 102, 18 ≤ y ≤ 62 | High | A zone proxy, not chance quality |
| Carries/distance | type, start/end | Yes | Count; sum Euclidean endpoint displacement in grid units | High | Displacement is not tracked running distance |
| Long passes/switches | pass.length, pass.switch | Yes, conditional | Use documented provider fields; configurable length threshold | Medium | Audit season coverage before treating absent flag as false |
| Shot creation / key passes | assisted_shot_id, shot_assist, goal_assist | Yes | Unique valid pass→shot links; cross-check flags | High | Include goals; do not count only non-goal shot_assist |
| Shot-linked xA proxy | assisted_shot_id, shot.statsbomb_xg | Derived | Sum xG of directly assisted shots per passer | Medium | Label as shot-linked xG assisted; not a provider xA model |
| Shots, goals, xG | shot.outcome, statsbomb_xg | Yes | Count shots/goals; sum valid xG | High | Own goals separate; penalty/open-play splits |
| Shots on target | shot.outcome | Yes | Proposed: Goal, Saved, Saved To Post | Medium | Saved Off Target excluded; blocks not automatically on target |
| Shot distance / inside box | shot.location | Yes | Distance to goal centre / box predicate | High | Grid units; no invented metric distances |
| Pressures | type=Pressure | Yes | Count; optionally sum duration | High | Activity, not pressing effectiveness |
| Counterpressures | Pressure, counterpress | Yes, conditional | Count Pressure with counterpress=true | High | Broader counterpress actions separate; provider five-second turnover definition |
| Interceptions | type, interception.outcome | Yes | Attempts plus success subset by documented outcomes | High | Do not conflate attempt and successful regain |
| Recoveries | Ball Recovery, recovery_failure | Yes | Count total and successful separately | High | Absence semantics must be schema-specific |
| Tackles | Duel, duel.type/outcome | Yes | Duel subtype Tackle, outcomes separately | High | Aerial duels excluded |
| Blocks/clearances | type, block.offensive | Yes | Count separately; remove offensive blocks from defensive tally | High | Avoid double counting paired events |
| Miscontrols/dispossessions | types | Yes | Separate counts and per-90 | High | Not a comprehensive possession-loss measure |
| Retention proxy | completion, losses | Derived | Show constituent metrics, lower-is-better loss rates | Medium | Not an overall pressure-resistance ability |
| Event involvements | player, type | Yes | Count selected actor events, list included types | High | Never call all events touches; paired receipts/carries inflate counts |
| Receiving / half-space receptions | Ball Receipt*, outcome, location | Yes | Completed receipt events in defined zones | Medium | Receipts also represent intended destinations; not continuous positioning |
| Half-space activity | location | Derived | Suggested y bands [16,32) and (48,64]; attacking-half activity reported separately | Medium | Project-defined bands; not official tactical-role labels |
| Average action position | player, selected event locations | Yes | Mean x/y by a declared on-ball event subset | High | Action location, not player tracking or formation position |
| Line-breaking passes | opponent line geometry | Not validated | Defer | Low | Through-ball tag is not proof of breaking an opponent line |
| Pressure resistance | pressure, outcomes, sequences | Partial | Defer ability score; report measured under-pressure outcomes only | Low | Conditional tagging and selection bias matter |
| Age/U23, market value, transfer availability | DOB, contracts/value source | No for cohort | Exclude | None | Never infer from nationality, name or current web biographies |
| Speed, off-ball runs, physical workload | tracking | No | Exclude | None | Events and 360 are not continuous tracking |

Proposed custom progression formula in StatsBomb grid units:

`D(x,y) = sqrt((120-x)^2 + (40-y)^2)`.

Count an eligible completed pass or carry only when `end_x > start_x`, `D_start > 0`, and `D_start - D_end >= max(10, 0.25 * D_start)`. Expose absolute threshold `10`, relative threshold `0.25`, completion requirement and open-play filter in configuration. This is an explicitly project-defined goal-distance reduction proxy, not a StatsBomb standard or a literature-equivalent metric. Test threshold boundaries, lateral/backward actions, near-goal geometry and coordinate transforms. Compare rankings under alternative thresholds before using it in composites.

An interpretable first profile can use passing, progression, carrying, shot-linked creation, shooting, defensive activity and spatial involvement. Retention should initially remain visible constituent metrics. Percentile composites must expose included features, direction, weights, peer population, minutes convention and missingness policy. No overall player rating is recommended. [Official field definitions](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf)

## G. Risks and validation gates

| Risk | Evidence / implication | Required response |
|---|---|---|
| Selective coverage | Catalog has full-sized and one-team/one-match samples | Require explicit cohort match manifest and exposure checks |
| Interval contradictions | Observed overlap in match 3913150 | Validate, reconcile, flag; exclude unresolved appearances |
| Stoppage-time ambiguity | Period clocks reset; valid appearances exceed 90 elapsed minutes | Preserve periods; support labelled elapsed and nominal conventions |
| Missing DOB | All 5,102 selected roster records lack DOB | Disable age filter; optional future licensed DOB source |
| Small role groups | Approx. AM peers: 5 at 450, 1 at 900 | Minimum cohort gate; show counts; no hidden broadening |
| Conditional fields | Absent true-only booleans can differ from unknown capability | Versioned semantics; distinguish false, null and unsupported |
| Event duplication in aggregates | Receipts/pass/carries and shot/block/keeper relations | Type-specific metric definitions; deduplicate linked creation |
| Camera/collection inference | off_camera and incomplete-video flags exist | Retain quality flags; do not assume complete observation |
| Team/style bias | Rates measure opportunity and tactical use as well as ability | Explain context; defer unsupported possession/league adjustments |
| Snapshot drift | Mutable repository and historical corrections | Pin commit and hashes, store schema/metric versions |
| Licence/publication | Commercial/redistribution restrictions | Code-only repository; attributed noncommercial analysis boundary |
| Metadata joins | Provider integer IDs are unrelated namespaces | Explicit reviewed crosswalks; no name-only auto merge |
| Missing-value ranking bias | Zero imputation invents poor performance | Require feature coverage; explicit unknowns and fixed comparison set |

Phase 2/3 validation must cover duplicate match/event/actor IDs, required IDs by event type, match/team/lineup relationships, finite numeric values, type-aware coordinates, chronological order, supported enum/schema changes, shot/pass links, period boundaries, starter/substitute consistency, overlap and dismissal handling. Reject negative durations and durations exceeding verified playable bounds rather than using a hard 90-minute maximum. Unknown fields should be recorded for review; unknown semantics must not silently enter analytics.

Season-wide content validation remains outstanding. No provider accuracy warranty, objective scouting validity or predictive recruitment performance is claimed.

## H. Proposed canonical model

Use namespaced string IDs, e.g. `statsbomb:player:4654`, alongside provider-native IDs. Separate a competition from its seasons and a player from team membership. Persist raw provenance once rather than duplicating full provider payloads in every feature row.

| Entity | Key and core fields |
|---|---|
| ProviderSnapshot | snapshot_id; provider; repository revision/API version; retrieval time; source URL/path; SHA-256; licence reference; declared capabilities |
| Competition | competition_id; name; country/region; gender; youth/international flags |
| Season | season_id; name; optional verified start/end dates |
| CompetitionSeason | competition_id + season_id; snapshot_id; coverage/stage notes |
| Team | team_id; provider/native ID; name |
| Player | player_id; names/nickname; country; DOB nullable with source and effective date |
| Match | match_id; competition/season; UTC/date/time provenance; home/away teams and scores; stage/status; data/fidelity versions; snapshot_id |
| MatchPeriod | match_id + period; start/end elapsed bounds; nominal base; extra-time/shootout indicator; quality flags |
| MatchRoster | match_id + team_id + player_id; shirt number; team-sheet status; source record |
| Appearance | match_id + team_id + player_id; starter; starting position; elapsed seconds; nominal minutes; minutes method/version; confidence/flags |
| PresenceInterval | appearance_id + interval index; start/end period and elapsed seconds; on/off reason; evidence and quality |
| PositionInterval | appearance_id + interval index; source position ID/name; broad group; interval bounds; evidence |
| Event | match_id + event_id; order; period; elapsed timestamp; display minute/second; possession ID/team; actor/team nullable; type; position; start coordinates; coordinate frame; duration/flags; snapshot_id |
| EventRelation | match_id + event_id + related_event_id; relation kind if established; generic relation retained otherwise |
| Pass / Carry / Shot / DefensiveDetail | event_id; typed endpoints/outcome/subtypes/flags/xG/assisted shot as applicable; shot z separate |
| PlayerMatchFeatures | player+team+match; raw totals; denominator; metric version; coverage/quality flags |
| PlayerSeasonFeatures | player+team+competition+season; totals/minutes; dominant-role distribution; version; cohort/snapshot ID |
| PeerCohort / Normalization | cohort definition; role; eligibility; fit population; feature stats, percentiles and version |
| ProviderIdentityMap | canonical entity + provider/native ID; match evidence; review status; effective dates |

Keep transfers/multi-team seasons possible through explicit team-season profiles; do not put a permanent team ID on Player. Competition metadata can live in a joined view satisfying the requested competition-season display shape.

Canonical locations should include normalized `x/120`, `y/80` for this provider and an explicit team-relative orientation. Keep original coordinates available through local provenance for debugging. A future provider adapter must establish its own scale and direction before conversion. Provider outcomes map to event-specific canonical categories; never use a single unqualified successful/unsuccessful mapping for all event types. Preserve unrecognized attributes in versioned local extension data while preventing them from silently influencing features.

## I. Proposed repository architecture

```text
football-recruitment-engine/
  README.md
  pyproject.toml
  dependency lockfile
  .gitignore
  .env.example
  config/
    dataset.toml
    metrics.toml
    cohorts.toml
    ranking.toml
  src/football_recruitment/
    domain/            # canonical entities, ID and capability contracts
    providers/         # StatsBomb first; metadata-only adapters separately
    ingestion/         # immutable snapshots, manifests, cache
    validation/        # type-aware checks, reports, quarantine
    preprocessing/     # coordinates, periods, presence/position intervals
    features/          # event -> player-match -> player-season
    normalization/     # eligibility, peer cohorts, feature directions
    profiles/          # transparent categories and evidence
    similarity/        # role-specific standardized nearest neighbors
    ranking/           # constraints, normalized weights, explanations
    evaluation/        # stability, sensitivity, ablations
    api/               # later minimal interface boundary
    cli.py
  tests/
    fixtures/          # synthetic; avoid redistributing source rows
    unit/
    integration/
  scripts/
  notebooks/exploration/
  data/{raw,interim,processed}/  # ignored; locally generated
  outputs/             # reviewed noncommercial reports; no raw downloads
  docs/
    DATA.md
    ARCHITECTURE.md
    FEATURES.md
    SIMILARITY.md
    RANKING.md
    EVALUATION.md
    LIMITATIONS.md
```

Use one installable package, not unrelated top-level source folders. Python 3.12+, pandas/NumPy, Pydantic, pytest and Ruff are a reasonable initial stack; Parquet/scikit-learn and one minimal UI dependency can be added when their phase needs them. Exact compatible versions and the lockfile are Phase 1 work. Avoid a database server, orchestration platform, cloud deployment or Docker requirement before the local pipeline works.

Provider contracts should separate capabilities. A metadata provider exposes competitions/matches/teams/person metadata as permitted; an event provider additionally exposes events/lineups. Unsupported operations raise an explicit capability error, not an empty list interpreted as no events. StatsBomb implements the event path first. CSV input must declare a schema and metric provenance before being accepted. Commercial-provider names are extension points, not pretend implementations.

For similarity, begin with within-position standardized per-90 features and Euclidean nearest neighbors; this avoids cosine's undefined zero-vector case as the default. Fit only on the eligible peer cohort, handle constant features, exclude self, break ties deterministically, and report largest standardized similarities/differences. Return distance plus a clearly defined transformed score if needed, never a probability of equivalent ability.

For ranking, require nonnegative finite weights and positive total weight; normalize weights to sum one. Use direction-aware peer percentiles with explicit tie convention. Score is the weighted sum of supported components, with contribution breakdown, weaknesses and cohort information. Reject requested unknown features or unavailable age constraints. Re-normalizing around missing features per player would make scores incomparable; use one declared feature set and coverage rule.

These are methodology proposals, not implemented or evaluated engines.

## J. Phase 1 implementation plan

Phase 1 objective: a reproducible repository and enforceable architecture boundary, **not full ingestion or analytics**.

1. Confirm cohort and publication scope below; create the project inside the agreed local directory without modifying existing ScoutLens work.
2. Create the installable package, Python version declaration, dependency lock, test/lint configuration, ignore rules, secret-free environment example and source/data licence distinction.
3. Add dataset configuration pinned to competition 37, season 281 and audited commit; configure paths, capability flags and provisional metric/cohort definitions. Do not silently use latest.
4. Define canonical entity contracts, nullable fields, namespaced IDs, provider capabilities and quality-status vocabulary. Review the minutes/role semantics before their implementation.
5. Save this audit into project documentation; document formulas, restrictions, unsupported features and milestone acceptance criteria. Seed the seven requested documents with real decisions and clearly marked future work.
6. Establish meaningful contract tests: unrelated provider IDs cannot collide, an event-less provider cannot claim event capability, unknown DOB is null and cannot pass a U23 constraint, and invalid interval ordering is rejected. Actual football calculation tests belong with the corresponding implementation phases.
7. Verify clean install, package import, test/lint execution and secret-free tracked files. Document commands that really run; do not advertise future ingestion/app commands as completed.
8. Create a local Git checkpoint if appropriate, then report Phase 1 results and remaining assumptions. No remote publication or deployment is included.

Later acceptance gates: Phase 2 produces verified immutable ingestion manifests and canonical files; Phase 3 certifies minutes/quality exclusions across the full cohort; Phase 4 adds tested versioned metrics; Phases 5–7 add cohort profiles/similarity/ranking; Phase 8 evaluates repeatability, threshold/weight sensitivity, feature ablation and held-out/subsample stability; Phase 9 adds a minimal interface. Football plausibility review must be documented separately from technical correctness. Ranking is decision support, not objective identification of the best footballer.

## Decisions and approvals

**Audit decisions made:** official sources only; no scraping; StatsBomb is the primary analytics source; football-data.org is optional context; coherent single-cohort comparisons; namespaced canonical identities; immutable revision/hash provenance; no age, value, tracking or LLM dependency; preserve uncertainty and quality exclusions; no application work before approval.

**Proposals needing your acceptance before Phase 1:**

1. WSL 2023/24 as the default cohort, rather than a men's-only or larger modern league.
2. Local noncommercial portfolio scope with code and attributed derived reports, excluding raw-data distribution and commercial deployment.
3. One Python package with capability-based provider boundaries; no mandatory football-data.org account.

**Decisions to finalize before their later phases:** elapsed versus nominal per-90 presentation; provisional 450-minute and ten-peer defaults; mixed-position mapping; progression thresholds; first profile features and weights; similarity distance/score presentation; and eventual Streamlit versus FastAPI interface. They are recorded now but need not all be settled to scaffold the repository.

**Stop condition reached.** No Phase 1 implementation has begun. Continue only after your instruction: **“Continue Phase 1.”**
