# Football Recruitment Intelligence Engine — final V1 handoff

Finalized locally on 2026-10-01. Python package version **1.0.0**. V1 is complete
through Phases 0–10 for noncommercial historical analytics on Windows/Python 3.12.
Technical validation is complete within that scope. One limited human qualitative
review, CASE-03, is complete. Expert/scout and predictive validation remain pending.
General model accuracy and transfer suitability have not been established.
V1.1 has not started.

## Canonical delivery and storage

The sole canonical final V1 package is **`football-recruitment-engine-v1-final.zip`**.
Verify it using **`football-recruitment-engine-v1-final.zip.sha256`** alongside it.
Both files are in the workspace's outer `outputs/` directory, beside the project
folder. Prior phase ZIPs, `football-recruitment-engine-v1.zip` and the review-tools
ZIP are historical checkpoints, not the final delivery.

The final ZIP contains one `football-recruitment-engine/` source root: application,
configuration, tests, documentation, lockfile, scripts, built wheel/sdist and final
technical acceptance evidence. `FILE_MANIFEST.json` inside that root records every
other packaged file's SHA-256. The external checksum covers the entire ZIP; it
cannot be embedded in that ZIP without changing its own value.

Provider payloads, derived player data, private reviewer notes, footage, local
environments, credentials and caches are excluded. Rebuild the dataset from the
pinned provider or use your existing verified cache. No source archive can imply
that data/footage redistribution rights have been granted.

Raw human review evidence remains private and is excluded from publication.

## Architecture

| Layer | Responsibility and boundary |
|---|---|
| `config`, `domain` | Strict TOML settings; typed canonical events, identities, teams, locations, lineups and intervals; unknowns retained |
| `providers` | Capability contracts and pinned StatsBomb mapping; future providers are separate adapters |
| `ingestion` | Official source acquisition/cache, immutable canonical artifacts, source hashes, roster/event checks and full-cohort publication |
| `preprocessing`, `validation` | Reconstruct presence and positional exposure; quarantine unresolved/contradictory appearances; verify quality-gated minutes |
| `features` | Aggregate eligible events into player-match/player-team-season sufficient statistics and explicit missingness-aware metrics |
| `normalization` | Positional eligibility, distinct-player reference spells, direction-aware percentiles and explained category scores |
| `similarity` | Pure candidate selection/scaling/distance; persist/replay neighbors and sensitivity diagnostics |
| `ranking` | Strict requirements, common complete benchmark, weighted percentiles, explicit filters/exclusions and replay |
| `evaluation` | Technical parity/integrity, repeated cohort perturbations and read-only human-review record checks |
| `api` | FastAPI loads a verified snapshot once; packaged HTML/CSS/JS expose four local views |
| `scripts` | End-to-end reproduction, deterministic review-pack generation and review-record checking |

Provider adapters map into canonical contracts; analytics never reads raw provider
JSON directly. Identity is separate from team membership. Each pipeline stage has
versioned, content-addressed manifests linking upstream artifacts/configuration.
Storage paths are bounded, immutable artifacts verified, cohort writes locked,
and failed/incomplete builds do not publish success manifests.

The application offers Player Explorer, two/three-player Comparison, Similar
Players and Recruitment Search. Requests use pure offline engines, make no provider
calls and do not mutate analytical data. The CLI binds IPv4 loopback with local
host/origin restrictions. There is no database server, cloud runtime, authentication
system, frontend framework or LLM service. [Architecture](docs/ARCHITECTURE.md),
[API/UI contract](docs/INTERFACE.md).

## Completed phases

| Phase | Delivered |
|---|---|
| 0 | Source-policy/coverage audit and coherent historical cohort selection |
| 1 | Python project, strict canonical contracts, configuration and provider interfaces |
| 2 | Pinned full-cohort ingestion, immutable canonical records and independent verification |
| 3 | Quality-gated presence, elapsed minutes and position intervals |
| 4 | Missingness-aware metrics and player-match/team-season aggregation |
| 5 | Positional profiles, peer eligibility, percentiles and category explanations |
| 6 | Explained similar-player retrieval and sensitivity diagnostics |
| 7 | Requirement-specific candidate rankings, contributions and filter semantics |
| 8 | Combined technical evaluation and twenty deterministic cohort perturbations |
| 9 | Verified local API and four functional browser views |
| 10 | Reproduction runner, demo, portfolio documentation and source delivery |
| Final handoff | Limited CASE-03 human notes, honest record checks, final docs/package and final technical acceptance |

Phase checkpoints in `docs/PHASE_*.md` retain their historical test counts. The
final status and final acceptance evidence supersede earlier delivery summaries.

## Dataset and cohort

StatsBomb Open Data: FA Women's Super League **2023/24**, competition **37**,
season **281**; revision **`4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`**.
The full baseline has 132 matches, 12 teams, 495,189 canonical events,
303 player/team-season profiles, 295 distinct players, 139 peer-eligible profiles
and 41 metric definitions. It is historical, not a current recruitment market.

Profiles remain keyed by player/team/competition/season. Broad positions are
GK, CB, FB, DM, CM, AM, W and ST. Peer eligibility requires at least **450 validated
denominator minutes**, **60% dominant positional exposure**, and a full player
season without quarantined appearances. Each reference group retains one spell
per player by greatest denominator minutes, then team ID. At least ten complete
peers are needed for supported comparisons. AM/CM shortages remain explicit.
[Data](docs/DATA.md), [profiles](docs/PROFILES.md).

## Important feature definitions

- Count/sum rates use `90 × aggregated total / validated denominator minutes`.
  Never average match rates. Default minutes are validated elapsed exposure,
  including stoppage time; excluded appearances contribute neither events nor minutes.
- Unknown contributing opportunities suppress complete metric values. No null
  becomes zero. Means/percentages remain in native units and are null without a
  sample; complete observed zero counts are valid zeros.
- Long passes are attempts with provider length **at least 30 yards**; this measures
  activity, not successful execution. Tackles are Duel subtype Tackle;
  interceptions are Interception events. Recovery, block and clearance counts
  remain separate event definitions. Pressures are activity, not effectiveness.
- Progressive passes/carries use the project distance-to-goal convention:
  gain at least `max(10 grid units, 25% of starting distance)`, forward movement,
  default completed passes and explicitly allowed open-play patterns. This is a
  project proxy, not a universal provider definition.
- Geometry uses the configured 120×80 grid, final-third x=80, and box
  x≥102 with 18≤y≤62. Grid displacements are not tracking distances in metres.
- Shot-linked xG assisted sums xG of validated linked shots, with duplicate/link
  safeguards. It is not an independent xA model. Nonpenalty xG excludes known
  penalties; shot-outcome completeness remains explicit.
- Action locations/involvements describe recorded usage, not tracking-based
  tactical roles or unique physical touches. Category composites use declared
  equal weights and complete common populations; no overall ability score exists.

The unchanged authoritative rules for all 41 metrics are in
[FEATURES.md](docs/FEATURES.md); minutes conventions in [MINUTES.md](docs/MINUTES.md).

## Similarity methodology

Compare complete vectors within the same eligible broad position/cohort. Exclude
every team spell of the query player; retain one spell per distinct candidate
player before completeness filtering. Require ten complete remaining candidates.
The fixed outfield vector contains twelve per-90 activity metrics: pass attempts,
long passes, carries, carry displacement, shots, nonpenalty xG, pressures,
interceptions, tackles, recoveries, final-third actions and box actions. GK uses
only passing volume and long passes.

Fit population-mean/population-standard-deviation scaling on candidates only.
Euclidean distance gives equal weight to active standardized coordinates;
constant coordinates are omitted with warnings. Return raw differences,
standardized differences and squared-distance contribution shares. Sort with
deterministic ID tie-breaks. The index `100/(1+distance)` is proximity, not
probability or ability. Query-specific scaling can make distances asymmetric;
indices are not comparable across queries/roles/scenarios. Robust-scaling and
other diagnostic variants remain separate from the unchanged baseline.
[SIMILARITY.md](docs/SIMILARITY.md).

## Ranking methodology

Eight illustrative positional requirements specify finite nonnegative weights
with positive total. Select one spell per player and one complete common
within-position reference population; missing active metrics exclude a player,
without per-player reweighting. Compute direction-aware midrank percentiles:
`100 × (count_less + 0.5 × count_equal) / n`; lower is preferred for miscontrols
and dispossessions. Normalize weights to sum to one; score is their weighted
percentile sum. Expose contributions, reference IDs and weaker requested dimensions.

Candidate minimum-minutes/team filters retain the fixed benchmark. Require ten
complete peers; constant active components suppress the requirement. Unsupported
age/market/contract filters are rejected. Sort by descending full-precision score,
then player/team IDs. The CB defensive-activity preset retains raw weights
**3 interceptions / 2 tackles / 1 long passes**. CASE-03 changes no definitions,
weights, selection or rankings. Scores represent activity priorities, not tactical
success, affordability or transfer suitability. [RANKING.md](docs/RANKING.md).

## Validation and test status

| Evidence | Final status |
|---|---|
| Technical tests, integrity, replay and local API parity | Complete for declared V1 scope; **220 tests pass** |
| Two isolated clean analytical rebuilds from pinned cache | All seven stage manifests and receipts match each other and the frozen V1 baseline |
| Perturbation diagnostics | Twenty reproducible cohort experiments; sensitivity evidence, not accuracy |
| CASE-03 human qualitative review | Completed raw review; **LIMITED** evidence coverage, one match with skipped portions |
| Other nine pilot cases | Unperformed; no additional reviews included in finalization |
| Expert/professional scout validation | Pending / NOT_PERFORMED |
| Predictive/outcome validation | Pending / NOT_PERFORMED |
| General model accuracy / transfer suitability | Not established |

CASE-03 preserves 30 human observations as YouTube replay timestamps. Continuous
duration, incidental model exposure, confidence, permission basis and observed
tactical role remain unknown/not assessed; numerical ratings are null. The reviewer
reported no deliberate model exposure. Initial notes and assistant comparison are
separate. Record checks pass with six explicit warnings, not expert certification.
No additional CASE-03 viewing is required for its limited assessment.

Final tests cover formulas, contracts, missingness, exclusions, tamper/replay checks,
HTTP parity and review-record boundaries using synthetic fixtures. One upstream
FastAPI/Starlette TestClient-httpx deprecation warning remains; no dependency change
was made to conceal it. Final evidence is `FINAL_VALIDATION.json` in the final
package, with the independent reproducibility proof and test report beside it.
Technical agreement does not establish football validity.

This public preparation retains a [sanitized validation summary](docs/VALIDATION.md)
and [baseline provenance](docs/BASELINE_PROVENANCE.json). Original machine-specific
reports and built distributions remain in the unchanged canonical ZIP, not this
publication directory. Original archive paths above describe that canonical ZIP.

## Known limitations and unresolved risks

The model measures event activity without possession, opponent, score-state or
tactical-context adjustment. Correlated metrics can amplify emphasis; broad
positions miss tactical roles; conservative missingness excludes useful dimensions
and small groups. Goalkeepers support distribution only. Historical season
exposure and minute thresholds affect availability. One convenience-selected,
nonprofessional qualitative sample cannot establish cohort-wide accuracy.

Current players/seasons, cross-provider identities, contracts, market values,
availability, transfers and tracking are unsupported. Official future source
access and redistribution rights are unresolved; football-data.org is not a V1
event provider. The original checkpoint had no code licence; Stage B selects MIT for owned code. Public analysis needs
provider attribution/logo compliance and a separate publication decision.

The loopback application has no production authentication/security/hosting design.
Large-cohort performance, production observability and cross-platform operation
beyond tested Windows/Python 3.12 are not certified. Provider schema drift,
dependency warning evolution and corrupted/missing caches remain operational
risks. Never bypass verification or use a stale receipt as proof of a failed run.
[LIMITATIONS.md](docs/LIMITATIONS.md), [DATA_LICENSE.md](DATA_LICENSE.md).

## Exact local run instructions

Extract the canonical ZIP and enter `football-recruitment-engine`. With Python
3.12 and uv available, run from that directory:

```console
uv sync --locked
uv run --locked fre check
uv run --locked python scripts/reproduce.py --serve
```

Open **http://127.0.0.1:8765**. First dependency installation and provider ingestion
need network access; no provider token is needed for the pinned public data.
Ctrl+C stops the application. Use `--port 8766` if 8765 is occupied; do not stop
unrelated services. Omit `--serve` for a build only.

With already installed dependencies and the existing verified raw cache:

```console
uv run --locked --offline python scripts/reproduce.py --offline --serve
```

A fresh extracted ZIP has no cache; offline mode fails deliberately without it.
The runner verifies every stage and writes `outputs/v1-reproduction.json`, including
the profile path. For the already built default snapshot, launch without rebuilding:

```console
uv run --locked fre serve --config-dir config --manifest data/processed/statsbomb/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/37-281/profiles-0.5.0/manifests/166bde6549efa2e42cff2ae9a1865fb707b56082cb6f67464d6ec950f653763a.json --port 8765
```

Final technical checks can be repeated with:

```console
uv run --locked pytest -p no:cacheprovider
uv run --locked ruff check .
uv run --locked ruff format --check .
```

To verify the outer ZIP on Windows, compare the value from
`Get-FileHash .\football-recruitment-engine-v1-final.zip -Algorithm SHA256`
with its adjacent `.sha256` file. [Full reproduction guide](docs/REPRODUCIBILITY.md).

## Recommended next development

First V1.1 task: **design expert football validation on fresh cases**, with explicit
rubrics, evidence limits and frozen V1 methods. Define what a qualified reviewer
can judge and what requires later outcome data; do not retune on CASE-03 and claim
independent validation. Additional CASE-03 viewing is not required.

Provider integration, entity resolution, deployment, UI/UX and an LLM scouting
interface are separately scoped deferred workstreams in [NEXT_STEPS.md](NEXT_STEPS.md).
V1 remains frozen until the user explicitly starts a new version.
