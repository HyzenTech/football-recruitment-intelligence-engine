# Frozen V1 static demo

Stage C adds a separate presentation layer. The analytical source, configurations,
original scripts and original tests remain frozen. No Python backend runs in the
browser; no JavaScript model, percentile engine or approximate ranking is introduced.

## Supported interactions

- Explorer: search all 303 player/team spells, filter positions, inspect validated
  minutes, eligibility, eight outfield category summaries and 41 metrics, including
  units, coverage, peers and explicit unavailable states. GK categories follow V1.
- Comparison: two or three distinct records, a selectable-metric percentile chart
  and full metric comparison. Each positional benchmark remains independent.
- Similarity: every offered profile has a verified Python result or exact status;
  display 1–10 exported neighbors. Show distance, proximity, differences,
  squared-distance shares and the complete candidate reference population.
- Recruitment: eight unchanged configuration presets, displaying 1–10 exported
  candidates. Show original/normalized priorities, contributions, weaker dimensions,
  reference records and exclusions. AM/CM insufficient-peer results stay unavailable.

Weights are fixed per exported scenario. The full local V1 application supports
editable weights; the static demo does not pretend to recalculate an arbitrary
complete reference population from Explorer percentiles. No age, market-value,
contract, injury or transfer-suitability filters are added.

## Private export and local preview

After reproducing the pinned V1 cohort, run from the repository with the locked
environment. Config and manifest must belong to the same existing verified build:

```console
uv run --locked python scripts/export_demo_data.py --config-dir <verified-build-root>/config --manifest <verified-profile-manifest> --output-dir outputs/static-demo-data
```

The exporter rejects an existing output directory, non-full-cohort data, a different
profile hash, changed frozen files or changed analytical configuration. It calls
the original profile verifier and similarity/ranking engines. A success manifest
is written last. A failed/incomplete export cannot be loaded as successful data.

For preview, copy `demo/` to an ignored scratch directory, put the exported files
in its `data/` subdirectory, and serve the scratch parent on IPv4 loopback:

```console
python -m http.server 8874 --bind 127.0.0.1 --directory <private-preview-parent>
```

Use a project-shaped subpath such as
`http://127.0.0.1:8874/football-recruitment-intelligence-engine/demo/`.
The provided source contract identifies the deterministic Stage C export. A changed
export schema requires regeneration, rechecking parity and updating this contract;
do not bypass integrity checks to make changed data load.

## Minimal public-field inventory — approval pending

| Asset | Fields / purpose |
|---|---|
| `players.json` | Player/team identity and names, position, validated minutes, eligibility, partial-season flag; selectors/search |
| `profiles/<identity-hash>.json` | Identity/cohort/version/minutes convention, minutes/dominant share/appearances/eligibility reasons; metric value/unit/percentile/peer count/coverage/status/direction; category score/status/metrics/peer count/weights/component percentiles |
| `similarity/<identity-hash>.json` | Exact Python query, status, scaling metadata, reference IDs, warnings, vector definition, maximum ten neighbors, full differences/contribution shares and distance/index |
| `ranking_examples.json` | Exact eight Python results: requirements, active/zero metrics, normalized weights, complete reference IDs, exclusions, candidate count, top ten candidates, values/percentiles/contributions/reasons/weaker dimensions/status/warnings |
| `metadata.json` | Frozen versions/source credit/revision/cohort counts, configuration hashes, export lookup paths, limits, validation status and publication status |
| `manifest.json` | Each asset's SHA-256 and byte count; schema, frozen profile hash and publication status |

No provider event rows, raw payloads, footage, source caches, review notes, ratings,
credentials or local paths are exported. Profile raw sufficient statistics and
non-displayed positional-duration arrays are omitted. Integrity metadata is not
permission to redistribute the derived values.

All derived JSON remains in ignored local scratch storage. `demo/data/` is ignored
as a second guard. The exporter rejects destinations in the tracked repository
outside ignored `outputs/`. No dataset is committed or bundled in the source kit.

## Loading, failure and accessibility

Only the manifest, metadata, selector index and selected profile load initially.
Profiles and similarity results load on demand and cache within the page. Recruitment
presets load when used. SHA-256/size checks precede parsing/rendering. Missing,
mismatched or corrupt data gives an explicit error; no synthetic fallback is used.

Labels, semantic headings, current-view navigation, a skip link, keyboard focus,
live result regions, mobile comparison bars, stacked mobile tables and reduced-motion
rules are included. The original local interface is unchanged.

## Publication gate

This is a **local verification preview**. All fetchable static JSON is public on
Pages. Resolve exact derived-data rights, provider registration and official-logo
attribution before a separate publication build. The current UI checks its
`LOCAL_PREVIEW_ONLY_RIGHTS_PENDING` status and displays it visibly. No remote,
deployment workflow or public Pages site is created by Stage C.
