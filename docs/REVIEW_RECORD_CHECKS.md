# Local review record checks

The read-only checker checks the structure of human review records. It never
certifies viewing, footage rights, expertise, football judgments or model validity.
It makes no network requests and does not edit the pack. Keep the original blank
template; save reviewer edits as a separate JSON file under ignored local storage.

```console
uv run --locked python scripts/check_review_records.py --pack-dir outputs/cb-review-0.1
uv run --locked python scripts/check_review_records.py --pack-dir outputs/cb-review-0.1 --results outputs/my-review.json
```

The JSON report goes to standard output. Exit 0 means the records satisfy the
structural checks, including when all cases remain `NOT_PERFORMED`. Exit 2 means
invalid input or record errors. Read `pending_cases`, each case's errors, warnings
and declared status; exit 0 does not mean the pilot is complete. Predictive
validation stays `NOT_PERFORMED`; expert validation is explicitly `NOT_CERTIFIED`.

## Fill the existing form

Keep the original case aliases. Use `NOT_PERFORMED`, `NOT_ASSESSABLE`, `LIMITED`
or `COMPLETED` as the reviewer-declared status. Completed can include unassessable
dimensions with null ratings. Unperformed/unassessable cases cannot carry ratings.
For performed records, provide reviewer identity, experience, ISO date, a boolean
prior-model-exposure disclosure, observations, context/uncertainty and next action.
For limited/completed reviews, provide low/medium/high confidence and explain its
basis in the context text. Post-reveal agreement needs an explanation in
`disagreement_reason`, including when there is no disagreement.

Ratings must be integer 1–5 or null, and match the case type. A rating requires
reported viewing for every player in the case, with a source citation in the
observation summary. This is a minimum traceability check; a human must assess
whether the cited evidence actually supports the judgment. Keep the initial
observations in a dated copy before revealing scores, as the review protocol
requires; this checker cannot reconstruct or verify that sequence.

Each `footage_sources_and_timestamps` entry uses this structure (illustrative
placeholders, not a viewing record):

```json
{
  "source_id": "S1",
  "player_id": "<canonical player ID from this case>",
  "team_id": "<canonical team ID from this case>",
  "match_id": "<canonical match ID from the frozen fixture locators>",
  "reference": "<official source URL or licensed file reference>",
  "authorization_basis": "<reviewer's basis for authorized access>",
  "observed_role": "<role actually observed, with uncertainty>",
  "content_kind": "full_match",
  "observed_intervals_seconds": [[350, 950], [1100, 1700]]
}
```

Use unique source IDs within each case. Cite each as `[S1]` in
`observation_summary`, alongside supporting/contradictory examples. Intervals are
actual video seconds continuously watched, excluding ads, breaks, skipped periods
and unattended playback. Sparse screenshots or access checks are not viewing
intervals. Use `highlights` for highlight sources. Never treat URL availability or
an authorization declaration as a verified licence.

Player/team/fixture identities must match the frozen pack locators. If other
fixtures are needed, document them separately and deliberately revise the pack
protocol; the checker does not silently expand the frozen selection.

The coverage report unions overlapping intervals within one source. For multiple
video editions of one player/fixture it conservatively takes the largest reported
source duration, because editions may have different clocks. It counts no
highlights toward substantial full-match exposure. Two distinct matches of at
least 60 minutes per player are a recommendation, reported as a warning when
absent, **not a universal pass threshold**. Even meeting it proves no football
validity. Human judgment must identify limited or unassessable dimensions.

Follow [the football review protocol](FOOTBALL_VALIDATION.md) for the actual review.

## Timestamped samples with skipped portions

A human may supply useful qualitative notes without continuous viewing intervals
or ordinal ratings. Preserve those notes as `LIMITED`, not `COMPLETED`. The
checker accepts the following narrow extension only for an unrated limited review:

```json
{
  "viewing_mode": "sampled_with_skips",
  "timestamp_basis": "youtube_replay",
  "observed_intervals_seconds": [],
  "watched_minutes": "unknown",
  "timestamped_observations": [
    {
      "timestamp": "1:02:32",
      "replay_seconds": 3752,
      "match_clock": null,
      "assessment": "Positive",
      "observation": "Good interception."
    }
  ]
}
```

These fields extend a source entry, whose source ID, player/team/fixture IDs,
reference, content kind and summary citation remain required. The checker verifies
the conversion from the supplied replay timestamp to replay seconds. It rejects
invented match-clock values in this sample format. Point references do not measure
viewing duration: never subtract the earliest timestamp from the latest to produce
minutes watched. Continuous duration is reported as `unknown`, with no qualifying
full-match exposure inferred. Sparse assistant stills are not human viewing notes.

For an unrated `LIMITED` case, confidence may remain `unknown` or `not assessed`.
Prior model exposure may remain `unknown` only with a nonempty
`model_exposure_disclosure` preserving the actual qualification. For example, "no
deliberate exposure" does not establish absence of incidental exposure or controlled
blinding. Unknown role or authorization basis stays explicit and produces warnings.
This preserves missing information, without certifying access rights.

Keep numeric rating fields null when no rating was supplied and record "not
assessed" in explanatory metadata; strings do not belong in integer rating fields.
The sample route cannot justify ordinal ratings or a completed review. Record any
assistant comparison separately rather than attributing it to the reviewer.
