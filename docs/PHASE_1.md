# Phase 1 checkpoint

Completed locally on 30 September 2026, Asia/Jakarta. Phase 2 has not started.

## Accepted scope

The instruction “Continue Phase 1” accepted the Phase 0 recommendation: WSL 2023/24, local noncommercial portfolio scope and one installable Python package with capability-based providers. No remote repository, publication, account registration or commercial rights were added.

## What changed

- Created the repository with Python 3.12 baseline, package metadata, CLI entry point, isolated environment, dependency lock and pinned build backend.
- Added strict canonical ID/entity/event/lineup/appearance/provenance contracts. Kept unknown birth dates and unresolved position ends explicit.
- Added metadata/event provider interfaces with capability checks; no provider adapters or network ingestion are implemented.
- Added four versioned TOML files: concrete dataset pin/hashes; provisional formulas/cohorts; deferred ranking with unsupported filters disabled.
- Added synthetic contract/configuration tests and copied the Phase 0 findings, inventory and evidence into portable project documentation.
- Added the seven requested methodology documents plus code/data rights boundary, ignore rules and an empty token example.

Runtime dependency: Pydantic 2.13.5. Test/lint baseline: pytest 9.1.1, Ruff 0.16.9. Build backend: Hatchling 1.32.4. All transitive versions/artifact hashes are in `uv.lock`. pandas/NumPy, scikit-learn, Parquet and UI packages are intentionally deferred until used. This keeps Phase 1 installation focused and reproducible.

## Verification

- **46 synthetic tests pass**, including provider identity collisions, metadata-only capability rejection, unknown-age/birthday boundaries, period reset/stoppage handling, invalid intervals/coordinates/numbers, required provenance, duplicate team-sheet IDs, disabled unsupported rankings, workspace path aliases/traversal and CLI error/status behavior.
- Ruff lint and formatting checks pass.
- `fre check` validates the actual pinned configuration and correctly reports data validation as not run. `fre status` reports no adapters and lists analytics/UI as deferred.
- Source distribution and wheel build successfully using the locked build toolchain. A fresh environment installed runtime dependencies with required hashes and installed the wheel, rather than using an editable source import. Import, canonical JSON-schema generation and CLI config validation succeeded outside the source checkout.
- Tracked-file hygiene was checked before the local checkpoint: source/docs/config/tests only; raw data, environments, generated distributions and token files are excluded. This is a targeted repository check, not a claim of exhaustive security certification.

## Remaining work and decisions

Phase 2: implement pinned StatsBomb fetching, immutable bytes/hashes, caching/resume, errors and canonical mappings. Add source-card/shot-endpoint/extension contracts before dropping information needed downstream. Phase 3 must reconcile all period/lineup intervals and the observed overlap; no minutes are certified now.

450 elapsed minutes, ten minimum peers, role share 0.6 and the custom progression rule are provisional config decisions, not evaluated defaults. Confirm/refine them when their phases begin. Age/value filters remain disabled. Choose a code licence and complete attribution/media requirements before public publication. Streamlit/FastAPI selection can wait until the interface phase.

The next recommended step is **Phase 2 — ingestion and canonical mapping**. This checkpoint stops at Phase 1.
