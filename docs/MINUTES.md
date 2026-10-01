# Appearance and minutes methodology

Version `presence-0.3.0`; implemented in Phase 3. This is an explicit project convention, not a claim to reproduce a commercial provider's published minutes statistic.

## Source semantics

The pinned [StatsBomb event specification](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/Open%20Data%20Events%20v4.0.0.pdf) and [lineup specification](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/doc/Open%20Data%20Lineups%20v2.0.0.pdf) define the evidence consumed by canonical ingestion. Period clocks reset, while lineup clocks use nominal global period bases. Late/early video or suspension flags prevent full-period certification.

## Event reconstruction

Require two matching team boundary records per playable period, zero Half Start clocks, positive agreeing Half End clocks, consecutive periods 1–2 or 1–4, and exactly eleven unique Starting XI actors per team. Events beyond the period end quarantine the whole match. Identity/schema failures prevent publication of a successful processed cohort.

Process state transitions in period/time/index order. Starters enter at period start. Substitution retires the outgoing player and introduces an unused replacement; an outgoing player temporarily off-pitch can still be substituted. Player Off closes presence; Player On requires a preceding temporary exit. Permanent exits, red cards and second yellows prohibit return. Bench/post-exit dismissals do not create playing time. Period resets retain active/temporarily absent states; half-time contributes no seconds. Period 5 shootouts contribute no minutes.

Each emitted presence interval is within one playable period and half-open. Ordinary actions exactly at an exit boundary are accepted for attribution because timestamp/index evidence does not establish sub-second physical presence. Actions clearly outside reconstructed presence quarantine the player's appearance. A roster-only entry never becomes a 90-minute appearance.

## Independent lineup cross-check

Position observations have second-level clocks. A source boundary can align to the nearest evidenced boundary within one second: period limits, the player's exit/return/substitution/card, or the team's tactical shift. Source and corrected canonical evidence remain separate. No arbitrary clipping of outside-period boundaries or repair of reversed observations is allowed.

Resolve open final boundaries only against the known final period end. Split cross-period observations at the observed period limits. Verify initial position agreement with the Starting XI. Detect position overlaps before any union, and compare source position coverage with event presence over every boundary segment. Equal total duration alone cannot establish agreement. A discrepancy quarantines the entire appearance, rather than silently summing, unioning or trusting one contradictory source.

Zero-duration position observations are diagnostic warnings and contribute no time when other evidence is consistent. Reversed/unparseable positions are errors. Invalid source card clocks can be resolved only from a unique matching canonical card event; dismissal discrepancies remain errors. Unclassified pass outcomes do not affect presence, but require a separate eligibility rule before passing metrics are built.

## Formulas and quality gate

For a validated player, elapsed seconds are `sum(end_seconds - start_seconds)` over disjoint per-period presence intervals. Elapsed minutes are seconds / 60. Added time counts, and recorded temporary absences do not.

Nominal minutes are the sum of each interval's intersection with `[0, 2700)` in periods 1/2 and `[0, 900)` in periods 3/4, divided by 60. This is a separately labelled nominal-window convention, not elapsed minutes capped at 90. Future per-90 metrics must use one declared denominator consistently.

Only appearances that pass both presence and position checks receive `VALIDATED`, positive playing seconds and versioned provenance. `NEEDS_REVIEW` appearances have null elapsed/nominal minutes and no usable presence/position intervals. Unused roster entries are explicitly excluded. Position-group duration uses the existing provisional `draft-0.1` ID mapping; role dominance and peer normalization remain Phase 5 work.

## Verification and limits

Input validation checks immutable raw/canonical hashes and record coverage before calculations. Processed verification independently checks hashes, model contracts, match partitions, quality counts, period bounds, disjoint intervals, position/presence timeline equality, duration totals and eleven-player capacity. Synthetic exact calculations test the reconstruction logic.

Validation means consistent with this declared method and available evidence. It does not establish complete video, tracking-derived physical presence, scouting accuracy, or feature-specific validity. Do not substitute zero minutes for quarantined records or normalize their events with another player's/appearance's denominator.
