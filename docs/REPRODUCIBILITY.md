# Reproducing V1

## Environment and complete run

Extract the source archive or use a checkout. Python 3.12 is required; Windows
is the validated platform. `uv.lock` pins dependencies. From the project root:

```console
uv sync --locked
uv run --locked fre check
uv run --locked python scripts/reproduce.py
```

The script invokes the same public CLI stages used throughout development. It
automatically passes each returned manifest path, independently verifies every
stage, and saves `outputs/v1-reproduction.json`. Full ingestion is required;
there is no implicit two-match demo or partial-cohort substitution. Evaluation
uses the configured default of twenty reproducible perturbations.

Only ingestion accesses the provider. Source bytes are downloaded directly from
official pinned paths, verified and cached under ignored `data/raw`. Do not use
offline mode on a fresh checkout. With installed dependencies and a verified
cache, use `uv run --locked --offline python scripts/reproduce.py --offline`.
Adding `--serve` launches the loopback UI after all verifiers succeed. An occupied
port fails visibly; choose `--port 8766` rather than stopping unrelated processes.

## Individual stages

Each build prints JSON containing its manifest path. Copy that value into the
next command when investigating a stage separately:

| Build | Input | Returned path key | Verifier |
|---|---|---|---|
| `fre ingest` | Configuration and official source/cache | `manifest_path` | `fre verify` |
| `fre validate` | Canonical manifest | `validation_manifest_path` | `fre verify-minutes` |
| `fre build-features` | Minutes manifest | `feature_manifest_path` | `fre verify-features` |
| `fre build-profiles` | Feature manifest | `profile_manifest_path` | `fre verify-profiles` |
| `fre build-similarity` | Profile manifest | `similarity_manifest_path` | `fre verify-similarity` |
| `fre build-rankings` | Profile manifest | `ranking_manifest_path` | `fre verify-rankings` |
| `fre build-evaluation` | Profile manifest | `evaluation_manifest_path` | `fre verify-evaluation` |

All commands after ingestion accept `--manifest PATH`; all accept `--config-dir
PATH`. The runner is available in the source archive/sdist, not as a separate
wheel console entry point. The installed wheel exposes `fre` and
`python -m football_recruitment` for individual stages.

## Stable artifacts and recovery

Provider bytes, canonical records, calculation settings and analytic artifact
versions determine the manifests. Package 1.0.0 retains the previously verified
analytic versions; changing packaging/documentation alone does not change their
hashes. The V1 full rebuild does have new downstream hashes compared with the
Phase 9 snapshot: its minutes report records the current cohort configuration
status `IMPLEMENTED` rather than the older `PROVISIONAL`. This propagates through
manifest lineage, while numeric artifacts remain unchanged. Use the new receipt
for the current build; older verified snapshots remain readable. Retrieval/run timestamps are operational receipts rather than model
inputs. A rerun may create new run reports while reproducing the same analytic
artifacts. The reproduction receipt is overwritten only after a successful run;
a previous receipt is not evidence that a later failed run succeeded.

The runner stops immediately when a CLI command fails, when ingestion is not
complete, or when a returned path escapes the project/is missing. Verified
artifacts remain available for retry. Missing/corrupt source inputs, schema
drift, invalid config, insufficient storage and integrity/replay failures must
be investigated rather than bypassed. Small peer groups are labelled analytic
outcomes, so they do not mean the pipeline itself failed.

## Tests and distributions

```console
uv run --locked pytest -p no:cacheprovider
uv run --locked ruff check .
uv run --locked ruff format --check .
uv sync --locked --group build
uv build --no-build-isolation
```

Tests use temporary synthetic sources. They do not require the real cohort or a
token. On Windows, use `--basetemp work/tests` if the default temporary directory
is inaccessible. One upstream TestClient/httpx deprecation warning is currently
visible; the assertions still pass. Avoid changing dependency versions merely
to hide it.

Install the wheel in a separate Python 3.12 environment, change outside the
checkout and run its CLI with an absolute config path. Run `fre verify-profiles`
on the built manifest and confirm `football_recruitment` resolves to that
environment's `site-packages`. Starting its API should serve the packaged HTML,
CSS and JS without reading frontend assets from the checkout. A wheel alone
does not include configuration or data.

The archive contains source, tests, docs, configuration and a data-free UI image.
It excludes environments, caches, provider payloads, player-derived outputs and
credentials. See [data rights](../DATA_LICENSE.md) before redistributing analysis.

## Final handoff evidence

The canonical delivery is `football-recruitment-engine-v1-final.zip` with adjacent
`.sha256`. It includes `FILE_MANIFEST.json` for packaged-file integrity and
`FINAL_VALIDATION.json` plus the final test, installed-wheel and reproducibility
reports. Older ZIPs retain historical checkpoints only.

Final acceptance repeats the complete 220-test suite, lint/format checks and two
isolated full builds through this runner. Each build begins without `data/interim`
or `data/processed`, uses identical copied configuration and verified pinned raw
cache, and runs offline. All seven stages execute their independent verifiers.
The two returned receipts and every stage manifest match the frozen V1 baseline;
the profile manifest remains
`166bde6549efa2e42cff2ae9a1865fb707b56082cb6f67464d6ec950f653763a`.
This checks clean analytical regeneration, not fresh network retrieval or football
accuracy. See [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md) for final scope/status.

## Portfolio source preparation

The public preparation has a separate publication file manifest and
`docs/BASELINE_PROVENANCE.json`; it does not contain the canonical archive's
`FILE_MANIFEST.json` or machine-specific XML/reports. The canonical ZIP is unchanged.
See [validation summary](VALIDATION.md) for independently repeated Stage B checks.
Public source distributions include MIT and third-party notices. Wheel contents
retain the original application source and include the selected code license.
No provider data or derived player tables are bundled.
