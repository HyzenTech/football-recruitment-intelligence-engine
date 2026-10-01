# Data strategy

## Accepted cohort

StatsBomb WSL 2023/24, competition 37 / season 281, revision `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. Configuration records the audited catalog/match hashes, counts and licence revision. Ingestion verifies these hashes; `fre check` only validates local configuration.

The [Phase 0 audit](audit/PHASE_0_AUDIT.md) sampled events. Phase 2 mapped all 132 event and lineup files, plus catalog and match list: 266 source files. There are 495,189 events, 5,102 roster entries, 336 distinct roster player IDs and 378 source card observations. No DOB is present. A roster entry need not mean an appearance; empty position arrays remain explicit.

## Snapshot and mapping contract

Fetch only pinned official paths. Preserve bytes with SHA-256, source URL, revision, licence revision and timezone-aware retrieval receipts. Bound request size, spacing, retries and workers. Reject corrupt cache, missing offline input, duplicate JSON keys and non-finite numbers. Do not replace failures with empty data. A cohort lock prevents concurrent writers; verified artifacts survive interruption. An incomplete run cannot publish a complete manifest.

Canonical IDs are namespaced. Coordinates are normalized from the provider's 120x80 actor-team attack frame, with no extra second-half flip. Shot endpoints retain their provider coordinate frame and height. Pass, carry, shot, defense, tactics, replacements and card evidence are mapped. Source-specific fields remain in versioned source attributes, including untyped freeze-frame evidence. Unknown fields/outcomes remain visible instead of becoming invented values.

Immutable canonical partitions and manifests are content-addressed. Run timestamps/cache counters live in separate run reports. Independent offline verification checks source receipts, hashes, counts and partition coverage. Two full offline runs produced the same manifest. See [Phase 2 evidence](PHASE_2.md).

## Minutes decision â€” provisional until Phase 3

Use elapsed on-pitch time including added time, excluding half-time and shootouts; label nominal regulation minutes separately. Both denominator and eligibility must follow the declared convention. Source position observations are evidence, not validated presence intervals. Phase 2 retains 61 zero-duration observations, 18 reversed intervals and two invalid card clocks with explicit flags and original source attributes. It makes no silent repairs. There are also 427 unclassified pass outcomes.

Resolve presence against period ends, substitutions, temporary exits and dismissals. Validate overlaps before interval unions. Match 3913150 has an observed first-half position overlap; a fixed 90-minute cap is unsuitable for elapsed time. Appearance reconciliation now excludes contradictory records; see [minutes method](MINUTES.md) and [full-cohort checkpoint](PHASE_3.md).

`data/` and generated `outputs/` stay local and ignored. No raw payload is redistributed. football-data.org remains optional metadata and is not used. See [rights boundary](../DATA_LICENSE.md).
