# Portfolio case study

## Problem and delivered system

Recruitment shortlists often hide how statistics became scores. This V1 builds
that chain explicitly: pinned football events become quality-gated exposure,
interpretable metrics, positional profiles, explained nearest neighbors and
weighted requirement rankings. Four local views make the calculations usable
without introducing an LLM or arbitrary overall player rating.

The project demonstrates data engineering, numerical reasoning, domain modelling
and application delivery. It implements standardized Euclidean retrieval and
multi-criteria ranking; it does not train a predictive scouting model or claim
outcome accuracy. The scope is a single historical WSL season for noncommercial
research, not a production club recruitment service.

## Decisions a reviewer can inspect

| Decision | Why it matters | Evidence in source |
|---|---|---|
| Pin official inputs and hash immutable artifacts | A rerun should use the same evidence | `ingestion/storage.py`, manifest verifiers, `config/dataset.toml` |
| Separate canonical contracts from provider adapters | Analytics can remain stable when another provider is added | `domain/models.py`, `providers/base.py`, `providers/statsbomb.py` |
| Derive event-state minutes and retain exclusions | Per-90 values need credible exposure | `preprocessing/minutes.py`, validation reports and tests |
| Preserve missing opportunity counts | Incomplete source evidence must not become a confident metric | `features/metrics.py`, feature aggregation/verifier |
| Use role peers and complete common populations | Comparisons need a declared, comparable benchmark | `normalization/engine.py`, profile replay tests |
| Exclude all query-player spells | A transfer must not become its own nearest neighbor | `similarity/engine.py`, deduplication/self-exclusion tests |
| Expose weights and contributions | Analysts should understand and change the requirement | `ranking/engine.py`, contribution and filter tests |
| Report unavailable stability attempts | Conditional overlap averages otherwise hide failures | `evaluation/engine.py`, repeated perturbation records |
| Verify before serving and compute locally | UI results must retain the pipeline's evidence boundary | `api/app.py`, HTTP tests and installed-wheel checks |

Paths above are relative to `src/football_recruitment`, except configuration and
tests. The [architecture](ARCHITECTURE.md) gives dependency direction and the
[reproduction guide](REPRODUCIBILITY.md) gives executable verification steps.

## Evidence and interpretation

The pinned baseline maps 132 matches and 495,189 events into 303 player/team
profiles, representing 295 unique players. 139 records meet the basic peer policy;
complete metric populations can be smaller. AM/CM shortages suppress relevant
outputs. Those exclusions are an intended part of the result.

220 tests cover formulas, boundaries, artifact integrity/replay, HTTP behavior,
and review-record boundaries. See [validation scope](VALIDATION.md).
Twenty reproducible player-cohort perturbations expose sensitivity: ST similarity
is available in 202 of 280 attempts and ST shooting ranking in 18 of 20 attempts.
This is evidence of small-cohort fragility, not a scouting success rate. See
[evaluation results](PHASE_8.md) for conditional overlap measures and their limits.

The interface provides source coverage, positional peer counts, metric differences
and score contributions. [The walkthrough](DEMO.md) shows how to interrogate those
outputs, including a missing metric and an unavailable requirement. The full
runner proves the chain can be repeated from verified source cache, and a
separately installed package proves delivery does not depend on source imports.

## What the evidence does not establish

One limited qualitative human review of Kadeisha Buchanan (CASE-03) is complete.
It found agreement around interceptions and defensive activity, while surfacing
positioning, possession risk and pressure/score-state context absent from the
activity model. This one sampled match with skipped portions did not justify
recalibration or establish general validity. Expert/scout and predictive validation
remain pending. Activity reflects opportunity and team style as well as the player;
possession adjustment, tactical context and correlated components need further
work. Scores do not establish ability, affordability, contract status or transfer
availability. Goalkeeper outputs cover distribution only.

The most useful next step is structured expert review: declare role-specific
expectations, review video independently of rankings, record disagreements and
their source, then decide whether additional legal data or context adjustment
would address them. Deployment, additional providers, learned roles and natural
language querying should follow that evidence rather than expand V1 by default.
