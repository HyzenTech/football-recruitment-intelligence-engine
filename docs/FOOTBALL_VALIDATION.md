# Centre-back football review protocol

Protocol `cb-review-0.1`. This prepares a local qualitative pilot, not a completed
expert review, predictive experiment or measured accuracy claim.

## Purpose and selection

Review five similarity pairs and five ranked candidates in the verified WSL
2023/24 cohort. The ranking requirement is explicitly **defensive event activity
plus long distribution**: interceptions, tackles and long passes weighted 3/2/1.
It does not measure every centre-back responsibility or transfer suitability.

Pairs are selected by descending validated minutes among peer-eligible CB team
spells. Use each query's closest available neighbor; skip duplicate unordered
player pairs and continue until five distinct pairs are selected. Candidates are
the top five under the existing `CB_defensive_activity` requirement. No selections
are changed after looking at footage. Some players can appear in multiple cases.
High-minute queries and top-ranked candidates make this a convenience sample;
there are no random controls or negative pairs. It cannot estimate general model
accuracy, false positives or predictive performance.

Initial cases receive deterministic shuffled aliases. The initial-review file
omits minutes, model distances, candidate ranks and scores. The protocol and
requirement are visible. This reduces one source of anchoring; reviewers still
know the selected players and this is not a controlled blinded study.

## Review order

1. Record reviewer identity, experience, date and any prior exposure to model
   results. Agree on the intended activity requirement before viewing scores.
2. Use historical fixture locators to find authorized footage. A locator confirms
   the player appeared in the match; it does not confirm a video exists. Record
   the source URL or licensed file reference, match ID, minutes watched and actual
   video timestamps. Sources begin as `NEEDS_SOURCE`.
3. Seek two distinct matches with substantial observed exposure for each player,
   preferably at least 60 minutes watched per match, covering different opponent
   contexts where possible. The supplied locators are the two largest validated
   exposures, not a claim of representative sampling. Do not rely solely on
   highlights. If coverage is inadequate for a dimension, record `NOT_ASSESSABLE`
   or a clearly limited observation rather than forcing a score.
4. Complete the initial observations before opening model explanations. Include
   supporting and contradictory examples and team/opponent context. Preserve this
   first pass; save a dated copy before the reveal.
5. Open model explanations, inspect component/distance evidence and record
   agreement, disagreement causes and confidence. Keep the original observations
   intact. Model/film disagreement can reflect different exposure or concepts,
   not necessarily an implementation defect.

## Observation rubric

| Dimension | What to observe | What event statistics cannot establish alone |
|---|---|---|
| Interception behavior | Anticipation, positioning, decisions, opportunities and missed chances | Defensive intelligence or success rate without opportunity context |
| Tackling behavior | Timing, choice to engage/contain, failed challenges, recovery after engagement | High tackling volume as inherently good defending |
| Long distribution | Frequency, intended destination, pressure, choices and execution | Long-pass count as passing quality or completion |
| Pair activity resemblance | Carrying, circulation volume, action locations, involvement and defensive actions | Equivalent ability, tactical role or team fit |
| Context | Team possession, line height, opponent, score state and match role | Season-wide context adjustment from this small review |

Exact season per-90 values cannot be independently confirmed by a small footage
sample. The review asks whether the explanation is consistent with observable
behavior and whether important trade-offs are missing.

For **pair resemblance**, use 1 = strong observed mismatch, 2 = mostly different,
3 = mixed resemblance, 4 = mostly similar, 5 = consistently similar across the
assessed behaviors. State which behaviors were actually assessable.

For **candidate requirement fit**, use 1 = clear contradiction of the stated
activity priorities, 2 = weak fit, 3 = mixed fit, 4 = good fit, 5 = consistently
strong fit across assessed priorities. This is a qualitative requirement judgment,
not a player ability rating. Leave it unassessable when key evidence is absent.

After reveal, **explanation agreement** uses 1 = substantial contradiction,
2 = mostly unsupported, 3 = mixed, 4 = mostly supported, 5 = strongly supported.
Confidence is low/medium/high with a written basis; confidence never substitutes
for footage references. The 1-5 anchors are project review conventions, not a
validated psychological or scouting scale.

## Record and act on disagreement

Tag the reason as source/identity mismatch, exposure/minutes, metric definition,
team/opponent opportunity, small sample, omitted behavior, correlated features,
weight preference, reviewer uncertainty, or another explained cause. Link every
actionable observation to footage evidence and, where relevant, a specific metric.

Calculated variants raise candidate minutes to 900/1350 and reduce the
interceptions weight to 1. They show whether conclusions depend on a boundary or
priority; they do not stand in for expert validation. Low-minute candidates may
be excluded even if their baseline score is high.

Summarize how many of the ten cases were reviewed, assessable, limited or still
unperformed. Preserve each case, source and uncertainty. Do not average ordinal
ratings into an accuracy percentage, claim general validity, or tune weights to
these same cases and call them an independent test. If a recurring issue has
clear evidence, propose one focused change and evaluate it on fresh cases.

No universal pass threshold is imposed on this pilot. A successful review produces
usable evidence and a justified next action, including the decision to collect
more evidence. Expert status remains `NOT_PERFORMED` until genuine observations
are recorded. Predictive validation remains `NOT_PERFORMED` regardless of film
agreement.

## Generate and store

```console
uv run --locked python scripts/build_validation_pack.py --manifest <verified_profile_manifest_path>
```

The generator verifies the full profile lineage, computes cases with the existing
engines and creates `outputs/cb-validation-pilot`. Packs must remain under ignored
local report storage. Existing destinations are rejected so reruns cannot erase
reviewer notes; choose a new `--output-dir outputs/cb-validation-pilot-repeat`.
Exact evidence is stored in JSON, explanations in Markdown and reviewer forms
in both formats. The protocol/generator are source-controlled; player-derived
packs and footage are excluded from source archives.

The project does not contact reviewers or acquire footage automatically. It
creates no public analytical demonstration. Provider and footage rights remain
separate; see [DATA_LICENSE.md](../DATA_LICENSE.md) in the source project.

Use the [read-only record checker](REVIEW_RECORD_CHECKS.md) on JSON reviewer edits
to find missing identities, source references and inconsistent ratings. It reports
self-reported coverage and advisory limits; it cannot certify viewing, expertise,
rights or football validity. An unchanged blank pack passes structural checks
while all ten cases remain unperformed.
