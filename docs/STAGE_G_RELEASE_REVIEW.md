# Stage G release review - local preparation

Local technical QA is complete. Public publication has NOT occurred, and Stage G
is not fully complete: provider registration/derived-data scope, private repository
visibility and exact external-action approval remain outstanding.

## Candidate source and exact destinations

- Recruitment source: local `release-review` branch, planned destination
  `HyzenTech/football-recruitment-intelligence-engine` (not created).
- Portfolio source: local `release-review` branch, intended update to
  `HyzenTech/hyzentech.github.io`, based on public main
  `3edc9778289d859c9a66712d62b6f80ce36026b6`, checked live on 2026-10-01.
- Planned project Pages URL: `https://hyzentech.github.io/football-recruitment-intelligence-engine/`.
- Planned article: `https://hyzentech.github.io/blog/football-recruitment-intelligence-engine/`.
- Proposed release: `v1.0.0 - Initial Portfolio Release`; metadata and notes are
  prepared as drafts in the adjacent `stage-g-review/` directory.
- No remote was added, repository created, branch pushed, PR opened, Pages
  workflow activated, portfolio merged, release published or provider contacted.

## Source-only boundary

The reviewed archives include code, frozen configuration/tests, safe synthetic
fixtures, documentation, empty-search screenshots, architecture SVGs and the
unchanged official logo preview rendition. They exclude provider/cache data,
derived JSON, data-backed captures, private CASE-03 notes, footage, environments,
credentials and build outputs. Review sources are not automatic publication approval.

The local demo's real JSON is in scratch storage only and still declares
`LOCAL_PREVIEW_ONLY_RIGHTS_PENDING`. All such fetchable files would become public
on Pages. No production deployment artifact containing those files is approved.

MIT applies to owned code/docs. Provider data and the logo remain separately
controlled. Logo source and portal usage label are recorded in
`STATSBOMB_LOGO_PROVENANCE.json`: official portal, External Use Approved,
800x122 unchanged preview PNG. This does not clear derived-data redistribution.
User explicitly confirmed no resource-centre registration or written permission.

## Checks performed

- 226 repository tests pass; Ruff clean. One upstream TestClient warning.
- Fresh offline full-cohort reproduction matches all seven prior stage receipts;
  profile hash remains `166bde6549efa2e42cff2ae9a1865fb707b56082cb6f67464d6ec950f653763a`.
- All 65 frozen analytical files unchanged.
- Export parity: 303 profiles, 303 similarity results, eight presets; 609 payloads
  / 9,854,382 bytes. Actual packaged exporter reproduces the exact deterministic
  export manifest `77797a95eb5841f153eb3fd881586da77f9dc80afb59e75bd0e6b9359964eb1c`.
- Extracted source distribution passes all 226 tests. Packaging now includes
  `demo/` and `FINAL_VALIDATION.json`, needed by the exporter and its tests.
  This fixes distribution completeness without changing analytical files.
- Wheel code bytes match frozen source. Source/sdist/wheel archives exclude data.
- Nine-page portfolio build succeeds; local links, cross-page anchors and image
  descriptions pass. No private capture assets in the default build.
- Prior desktop/tablet/mobile, keyboard, theme and numerical example checks are
  retained. New logo and source-credit links checked in desktop/mobile preview;
  planned project-path demo loads and retrieves real results with no console errors.
- Source and all locally reachable historical text blobs scanned for credential
  signatures and absolute user paths: no findings. This is a bounded pattern scan,
  not an exhaustive guarantee. Original portfolio history was a shallow checkout.
- Public owned repository list has 17 entries, no matching recruitment repository.
  No installed accounts/private repositories are exposed by the connector;
  private duplicate coverage is NOT established.

## Remaining publication work

Resolve registration and a defensible exact public-data/assets scope. Complete
private duplicate/access checks. Review final commits, patches, archives and desired
visibility. Obtain explicit authorization for repository creation/push, portfolio
merge/deployment and release publication. Real-data demo publication needs a
separate reviewed export contract and deployment artifact; do not bypass current
integrity/privacy status. Live Actions and Pages checks occur only after deployment.

See the adjacent review kit: `LOCAL_QA.json`, `REPRODUCTION_QA.json`, source/package
archives and checksums, metadata/release-note drafts and `POST_APPROVAL_RUNBOOK.md`.
The code-CI workflow is a non-installed draft. Recruitment CI and Pages deployment
have not been remotely tested. Existing portfolio deployment configuration is preserved.
