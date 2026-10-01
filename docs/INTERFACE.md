# Local interface and API

Run `fre serve --config-dir config --manifest <profile_manifest_path> --port 8765`
from the project root after installing the locked environment. Open
http://127.0.0.1:8765 after startup completes. Ctrl+C stops the process.
The manifest path comes from `fre build-profiles`; the source archive contains
no dataset, so a new checkout needs ingestion and the documented build stages.

Startup verifies profile hashes and replays the upstream feature/minute lineage
before accepting requests. A failed verification stops startup. Profiles and
configuration are held in memory; restart to load another snapshot. Request
handlers do not download provider inputs or save derived results.

## Views

- Player Explorer: name/team search, position filtering, team-spell identity,
  validated minutes, role shares, eligibility, categories and all 41 metrics.
  Coverage, complete peer counts, and unavailable statuses remain visible.
- Comparison: two or three distinct player/team records. Each percentile retains
  its own positional population; different positions trigger a benchmark warning.
- Similar Players: position-constrained complete vectors, query self-exclusion,
  distance, transformed proximity index, and metric differences.
- Recruitment Search: eight starting requirements, position/minutes filters,
  editable nonnegative weights and candidate limit. Results show normalized
  weights, contributions, exclusions and the full reference benchmark.

Age, market value and contract filters lack source evidence and are unavailable.
No overall ability rating, recommendation model, transfer availability claim,
LLM call, or predictive scouting validation is introduced.

## HTTP contract

| Route | Input | Result |
|---|---|---|
| GET `/api/meta` | None | Provenance, cohort counts, requirements and limits |
| GET `/api/players` | Optional `q`, `role` | Matching record summaries |
| GET `/api/profile` | `player_id`, `team_id` | Full profile; unknown record 404 |
| POST `/api/compare` | `players`: 2-3 player/team objects | Profiles and warnings |
| GET `/api/similar` | Player/team IDs, optional `top_k` 1-50 | Existing similarity engine output |
| POST `/api/rank` | Strict `RankingRequirement` JSON | Existing ranking engine output |

Invalid schemas return 422; invalid calculation constraints return 400.
Insufficient peers return a labelled result with no fabricated candidates.
The API uses the same calculations as the offline commands. POST routes compute
only; they do not persist mutations. Unknown request fields are rejected.

The CLI binds only IPv4 loopback. Host validation and same-origin checks apply;
responses disable caching and restrict scripts/styles/connections to local assets.
Static HTML/CSS/JS are packaged with the wheel, without a CDN or font service.
Swagger UI is disabled; `/openapi.json` describes the local API. This has no
authentication and is intended solely for a trusted local machine. Hosting,
multi-user access, and public deployment require a separate design and approval.

See [profiles](PROFILES.md), [similarity](SIMILARITY.md),
[ranking](RANKING.md), and [evaluation](EVALUATION.md) for formulas and limits.
