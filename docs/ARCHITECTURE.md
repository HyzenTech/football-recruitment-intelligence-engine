# Architecture

![Frozen V1 data flow, analytical engines and verified local interface](../assets/architecture.svg)

The diagram depicts implemented V1. The Pages export layer is future portfolio
work and is deliberately absent. Technical evaluation audits recomputed outputs;
it is not a football accuracy certificate or a live dependency of API requests.

## Implemented V1 (Phases 0-10)

One Python 3.12 package provides strict canonical contracts, namespaced IDs, provenance, provider interfaces, TOML settings, a StatsBomb adapter, immutable ingestion and offline artifact verification. Canonical top-level fields are strict; source-specific extensions are deliberately retained as JSON evidence. Unknown values remain null and administrative events may lack actors/locations.

`domain` has no provider HTTP or analytics dependency. `providers.base` returns canonical types and enforces event/lineup capabilities. `providers.statsbomb` implements the selected pinned cohort. `ingestion.storage` verifies receipts and bytes, bounds downloads and enforces immutable writes. `ingestion.pipeline` performs basic roster/event identity checks and publishes a manifest only after all requested matches succeed. `ingestion.verification` independently verifies stored hashes and counts.

`TeamLineup` preserves roster metadata, source cards, position observations and unresolved boundaries. Flagged contradictory observations retain original evidence; they cannot masquerade as validated minutes. `PresenceInterval` and `PositionInterval` require ordered, resolved boundaries. `preprocessing.minutes` reconstructs event presence and cross-checks position observations. `validation.pipeline` publishes only quality-gated intervals and explicit quarantined appearances; `validation.verification` checks output integrity and interval invariants.

Events include period elapsed time, display clock, possession, actor/team and typed pass/carry/shot/defensive/tactical details. Normalized `Location` uses a 0..1 actor-team attack frame. `ShotEndpoint` separately retains provider x/y/z. Replacement IDs, dismissals and video/boundary flags support later reconciliation. Untyped provider extensions, such as freeze frames, require a typed contract before analytics uses them.

## Dependency direction

Adapters -> canonical domain; ingestion -> adapters/snapshot store; preprocessing -> canonical records; features -> validated appearances/events; normalization -> eligible feature cohorts; profiles/similarity/ranking -> canonical feature artifacts; API/UI -> application services. Analytics cannot read provider JSON directly. Every stage keeps provenance and version metadata.

Player identity is separate from team membership. Transfers require team-season feature keys. Downstream artifact versions and manifest lineage are explicit.

## Settings and storage boundary

Dataset configuration is concrete and pinned. Metric definitions are implemented; cohorts are `IMPLEMENTED` with explicit project conventions; ranking is `IMPLEMENTED` through named requirements, with global ability weights empty. Project-relative storage paths must be distinct and avoid traversal/overlap. Writers and verification resolve paths to reject symlink/junction escapes. A per-cohort advisory lock releases when the process exits, including interruption. Config checks create no files and download no data.

## Deferred

football-data.org/CSV/commercial adapters remain extension points. No cloud service, database server, Docker, frontend framework or LLM dependency is installed.

`features.metrics` defines sufficient statistics and formulas. `features.pipeline` consumes verified canonical events and validated exposure, groups transfers by player/team/season, and emits missingness-aware tables. `features.verification` checks integrity, exposure census, aggregate statistics and derived rates.

`normalization.engine` contains pure positional exposure, reference selection and profile calculations. `normalization.pipeline` joins verified feature artifacts to validated positional intervals, checks partial-season lineage, publishes immutable artifacts and replays them for verification. No analytics reads raw provider JSON.

`similarity.engine` selects complete within-role candidate vectors, excludes query-player spells, fits candidate-only scalers and returns explained Euclidean neighbors. `similarity.evaluation` performs declared sensitivity experiments. `similarity.pipeline` persists and replays both outputs against verified profiles. `config/similarity.toml` holds versioned feature sets/scaling, alongside the four existing configuration files. No new runtime dependency is required.

`ranking.engine` validates strict scouting requirements, selects one common complete positional population, computes direction-aware weighted percentiles and returns contributions/exclusions. Candidate filters retain the benchmark population. `ranking.pipeline` persists and replays rankings plus sensitivity diagnostics. Requirements are modelled in `config` and versioned in `ranking.toml`; the CLI accepts named presets or strict JSON requests.

`evaluation.engine` audits recomputed baseline outputs and performs repeated player-level cohort perturbations, preserving explicit unavailable outcomes and data-only review limits. `evaluation.pipeline` persists/replays the full report and input configuration. External archetype and predictive validation are not inferred from these checks.

`api.app` loads verified profiles once during startup and delegates requests to the pure analytics engines. Packaged HTML/CSS/JS provide four local views. The CLI binds IPv4 loopback; request handlers do not write data or access providers. `scripts/reproduce.py` chains existing CLI build and verification stages, stops on errors, and records manifest paths in an ignored local receipt.
