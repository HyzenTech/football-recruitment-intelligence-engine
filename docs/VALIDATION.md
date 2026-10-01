# Validation evidence and its limits

Checked during local Stage B preparation on 1 October 2026.

## Independently repeated checks

- A fresh Python 3.12.14 environment installed the unchanged `uv.lock` with
  `uv sync --locked --group build`.
- **220 tests passed**, zero failures/errors. One upstream Starlette TestClient /
  httpx deprecation warning remains visible; dependencies were not changed to hide it.
- Ruff lint and format checks passed.
- All 65 files in `src/`, `config/`, `tests/`, original `scripts/` and `uv.lock`
  match the canonical V1 file hashes. See [baseline provenance](BASELINE_PROVENANCE.json).
- A new source distribution and wheel build succeeded with MIT license metadata.
  Wheel application bytes match the canonical source; no analytical code changed.
- Initial recursive publication/archive scans found no matching credential strings,
  private review files, absolute user paths or email addresses. Provider data,
  caches, player-derived tables and machine-specific reports are excluded.

- A separate environment installed the new wheel, with locked runtime dependencies.
  Imported code resolved to `site-packages`, outside the source checkout.
  Startup loaded the verified full cohort: 303 profiles, 295 players and 139
  eligible profiles. Packaged HTML/CSS/JS and profile/similarity/ranking HTTP
  parity checks passed against the unchanged Python engines.

- One additional clean offline analytical rebuild completed during Stage B using
  a copied verified pinned cache, with initially empty interim/processed outputs.
  All seven stage manifests and the resulting reproduction receipt match the
  frozen V1 baseline. This repeats analytical regeneration, not new provider
  retrieval. The original two-build proof remains separate canonical evidence.

## Canonical final acceptance

The original final ZIP contains test, wheel and two-clean-build evidence. Its
seven analytical manifests and reproduction receipts matched each other and the
frozen V1 baseline. Those original machine-specific reports are retained privately,
not republished here. The canonical ZIP/checksum remain unchanged.

Technical checks cover integrity, formulas, replay, exclusions, missingness and
API parity. Twenty deterministic cohort perturbations measure sensitivity, not
prediction accuracy. CASE-03 is one limited qualitative review of a sampled match;
expert/scout and predictive validation remain pending. General model accuracy and
transfer suitability have not been established.

This summary intentionally omits machine hostname, absolute local paths and raw
human observations. It is a publication summary, not the original test report.


## Stage C static presentation acceptance — 2026-10-01

The full suite passes: 226 tests, comprising all 220 original tests and six new
export-boundary tests, with the same upstream TestClient deprecation warning.
The new Python files pass Ruff lint/format checks; static JavaScript syntax checks pass.
All 65 frozen file hashes remain unchanged.

Independent comparison against the Stage B clean-rebuild artifacts verifies all
303 projected profiles field by field, all 303 full similarity results exactly,
and all eight full ranking results exactly. All 609 payload hashes and byte counts
pass. A repeat export produces identical manifest bytes and payload digests.

Browser checks cover the four views, two/three-player comparisons, role-specific
benchmarks, missing passing metrics, goalkeeper distribution/unsupported shot
stopping, empty search, AM insufficient peers and rejected neighbor limits.
Desktop, tablet (768 px) and mobile (375 px) render without document overflow;
an unavailable-chart message overflow found at tablet width was corrected.
Missing data and corrupted profile bytes both fail closed with disabled controls.
Labels, keyboard focus, semantic tables and progress labels were inspected;
this is not a formal assistive-technology audit.

The demo works from a repository-shaped subdirectory with relative asset paths.
This is local browser evidence, not a deployed GitHub Pages check. Provider-derived
JSON and data-backed screenshots remain private and absent from the source kit.
See [machine-readable summary](STAGE_C_VALIDATION.json).
