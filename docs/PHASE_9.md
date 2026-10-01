# Phase 9 checkpoint - local interface/API

Completed locally on 2026-10-01. Package 0.9.0. Scope stops before Phase 10
portfolio polish; no remote publication or deployment.

## Acceptance

189 tests pass, including HTTP contract/validation, local host/origin boundaries,
engine parity, profile immutability during requests, and startup failure without
fallback. The HTTP fixture isolates startup loading; the full real-data startup
and installed-wheel checks separately exercise actual lineage verification.
Lint and format checks pass. Test output includes an upstream TestClient/httpx
deprecation notice and a Windows pytest-cache permission warning; neither affects
the passing assertions.

The verified WSL 2023/24 snapshot exposes 303 player/team records, 295 unique
players, and 139 peer-eligible records. Profile manifest SHA-256 remains
`1a3841c50f9a32670503871a60c3f2945637acca6e55976f0b53f3340bd59ae0`.

Real HTTP responses exactly match the offline engine for Maya Le Tissier's
similarity query and all eight configured recruitment requirements. Six return
ten candidates; AM/CM correctly return insufficient peers. The separately
installed wheel loads and verifies all 303 records outside the checkout and
contains all three frontend assets.

## Browser checks

Player Explorer displays sourced minutes, missing passing metrics and peer
counts. Two-player comparison calculates correctly; adding Ella Toone as a third
player shows the different-position warning. Similarity returns ten neighbors for
Maya Le Tissier and suppresses Ella Toone's undersized AM population. Recruitment
returns ranked CB candidates, changing an interception weight changes normalized
priorities, and the AM preset returns no candidates. The narrow 623-pixel layout
was checked and corrected to keep long player selectors inside the viewport.

Local acceptance JSON and a UI preview are saved outside the source archive.
Source archives and distributions exclude provider payloads and generated
player data. The interface remains local and noncommercial. Expert/film-based
and predictive validation are still unperformed.

See [interface contract](INTERFACE.md) for commands, routes and runtime boundaries.
