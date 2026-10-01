# Phase 10 checkpoint - portfolio delivery

Completed locally on 2026-10-01. Package **1.0.0**. Phases 0-10 are complete for
the scoped local V1; expert/predictive validation and future product work are
explicitly deferred. No public repository, deployment or package publication.

## Delivered

- README with motivation, architecture diagram, data scope, metric/similarity/
  ranking methods, measured evaluation limits, setup and roadmap.
- Source-controlled UI screenshot of the actual empty-search state, without
  player statistics. Real-data review screenshots remain outside the archive.
- [Portfolio case study](PORTFOLIO.md), [five-minute demo](DEMO.md) and
  [reproduction guide](REPRODUCIBILITY.md).
- `scripts/reproduce.py` chains full ingestion, six downstream builds and their
  verification commands, records returned manifest paths, and optionally starts
  the loopback app. It uses existing engines rather than duplicating calculations.
- Current architecture/limitations and CLI status; versioned source/wheel/sdist.

## Verification

189 tests pass, with one upstream TestClient/httpx deprecation warning. Lint and
format checks pass. Two complete offline runs from verified cache reproduce
identical receipts and manifests. The missing-cache case returns exit 2 before
validation and produces no success receipt; original failure diagnostics remain
visible. A separately installed wheel, running outside the checkout, serves the
verified 303 profiles and packaged HTML/CSS/JS. Its OpenAPI version is 1.0.0.

The source distribution contains the runner and data-free image; generated
datasets, player outputs, caches and credentials are excluded. Source hygiene
and local documentation links are checked before the source checkpoint.

## Current default lineage

| Stage | Manifest SHA-256 |
|---|---|
| Canonical ingestion | `380994c3de5306aad9fd7f0e09086264a26398d7072e62015df6d425bd94c935` |
| Minutes | `8618e469e04a0f959b887ea02a2310a0d4a022657fd9b714f2380227d0001687` |
| Features | `4d81284077268ca70507bc50128b9f339c0b6828e93b401c6bef86a2ab818b4e` |
| Profiles | `166bde6549efa2e42cff2ae9a1865fb707b56082cb6f67464d6ec950f653763a` |
| Similarity | `75563e30f0b243a38b5fdac728ba456fbeae544f5ef91ca542d6fd602be3bd7d` |
| Ranking | `2d8bdd24fbbf400a18cb7a444d76779a580071faecea560d26ddddb4c2d4b907` |
| Evaluation | `fc466587ca508108ba33d32f1490d1a4d3df2dd488776d841048adc9dcd02438` |

The full rebuild uses the current cohort configuration status `IMPLEMENTED`;
the original Phase 3 report used `PROVISIONAL`. This metadata changes the minutes
report hash and downstream lineage. The minutes, feature and profile artifact
lists/hashes remain exactly identical to their older checkpoints. Subsequent
current-config reruns reproduce identical new manifests. Older snapshots remain
valid and have not been deleted or rewritten.

## Remaining evidence boundaries

Scores describe event activity and illustrative requirements in a historical
cohort. AM/CM shortages and conservative missingness persist. No expert review,
predictive accuracy, age/market/contract data, goalkeeper shot stopping or current
transfer availability has been established. Code licence selection and any public
data-backed presentation remain separate decisions. Future work should start
with structured football review rather than automatically extending features.

## Final V1 handoff

The final delivery is `football-recruitment-engine-v1-final.zip` with its adjacent
SHA-256 checksum. Earlier packages and the verification above are historical
checkpoints. The final complete suite has **220 passing tests**, with lint and
format checks passing. Two isolated clean analytical output roots, using the same
verified pinned raw cache, reproduce the same seven stage manifests and receipts
as each other and the current V1 baseline.

CASE-03's limited nonprofessional human qualitative review is complete: one
player-focused match sample with skipped portions, 30 preserved YouTube timestamp
observations, unknown continuous duration and no inferred numerical ratings. No
additional CASE-03 viewing is required. Expert/scout and predictive validation
remain pending; general accuracy and transfer suitability are not established.
Original analytical definitions, selections, weights and rankings remain unchanged.

The [final handoff](../PROJECT_HANDOFF.md) documents the architecture, baseline,
validation evidence, limitations, canonical package and exact local instructions.
[NEXT_STEPS.md](../NEXT_STEPS.md) scopes deferred work. V1.1 has not started.
