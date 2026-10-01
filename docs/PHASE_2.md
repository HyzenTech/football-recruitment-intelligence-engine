# Phase 2 checkpoint — ingestion and canonical mapping

Completed 2026-09-30. Package version 0.2.1; mapping version `statsbomb-canonical-0.2.1`. Scope stops before appearance/minutes reconciliation.

## Actual cohort results

Pinned StatsBomb revision `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`, WSL competition 37 / season 281.

| Evidence | Result |
|---|---:|
| Matches / teams | 132 / 12 |
| Verified raw source files | 266 |
| Canonical partitions | 266 |
| Events | 495,189 |
| Roster entries / distinct player IDs | 5,102 / 336 |
| Card observations | 378 |
| Zero-duration position observations | 61 |
| Reversed source position intervals | 18 |
| Invalid source card clocks | 2 |
| Unclassified pass outcomes | 427 |

Every requested match mapped successfully. Unknown pass outcomes are retained with their source label and an explicit flag, rather than forced into completion/failure. Contradictory position/card clocks retain original source evidence; strict usable presence intervals remain separate. These counts are observations, not player metrics.

## Reproducibility

Full offline runs `20260930T132027_118209Z.json` and `20260930T132657_590375Z.json` both reused 266 verified source files, downloaded zero files and produced manifest SHA-256:

```text
380994c3de5306aad9fd7f0e09086264a26398d7072e62015df6d425bd94c935
```

The manifest lives beneath `data/interim/statsbomb/<revision>/37-281/statsbomb-canonical-0.2.1/manifests/`. Run reports live in ignored `outputs/ingestion_runs/`. Source receipts, raw files and canonical partitions are local and excluded from Git/source archives. A fresh checkout needs ingestion before these commands can verify data.

An earlier full run against stricter mapping 0.2.0 rejected six matches with inconsistent source clocks. Mapping 0.2.1 preserves flagged observations without inventing repairs. Cached source bytes were reused for the successful run.

## Acceptance

77 synthetic tests passed; lint and format checks passed. The source distribution and wheel built successfully; the wheel was installed and its CLI/imports checked outside the source checkout. Tracked-file and archive checks excluded raw data, environments and credentials. Tests cover complete/partial runs, deterministic offline reuse, corruption and tampering, retry bounds, failures/resume, orphan receipts, immutable collisions, lock release, path containment, strict JSON and event/lineup mapping. No raw provider fixtures are redistributed.

Independent `fre verify` checks pinned metadata hashes, source receipts/bytes, canonical hashes/row counts, aggregate counts and partition coverage. Verification is offline and deliberately reports canonical quality `UNVALIDATED` and minutes validation `not_run`. It certifies artifact integrity, not football validity.

## Next phase

Phase 3 must reconcile starters, substitutions, temporary exits, dismissals, period boundaries and positional overlaps across all matches. Quarantine unresolved contradictions and report exclusions. No player minutes, per-90 features, rankings or UI are produced here.
