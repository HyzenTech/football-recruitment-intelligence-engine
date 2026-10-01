# Deferred development after final V1

V1 is finalized. This is a roadmap, not authorization to start V1.1, contact
reviewers, acquire footage, integrate accounts, pay for data or deploy. CASE-03's
limited human review is complete; no additional viewing is required for it.
Its observations did not change V1 features, weights or rankings.

## 1. Human/expert football validation — recommended first task

Design a qualified expert/scout validation protocol on fresh cases, preserving the
V1 baseline and distinguishing activity resemblance, requirement fit and overall
quality. Specify reviewer qualifications, prior model exposure, supporting and
contradictory evidence, assessable dimensions and coverage limits. Plan comparison
or negative cases where useful; convenience samples cannot estimate general accuracy.
Use authorized evidence and obtain approval before external contact/acquisition.

Acceptance: a documented protocol, independent case selection and a plan for
reporting disagreement, unavailable evidence and uncertainty. Later execution is
separate. Predictive validation additionally needs a defined future outcome,
time-separated evaluation and a defensible baseline; ordinal reviews are not an
accuracy percentage. Do not reopen CASE-03 to satisfy a universal viewing threshold.

## 2. Current-player/current-season data provider integration

Audit one legally usable event provider for current coverage, schema, freshness,
identifiers, minutes/lineup support, cost and storage/redistribution rights. Metadata
alone cannot replace event data. Do not assume V1's public historical source meets
current recruitment needs or that a future metadata adapter supplies analytics.

Acceptance: a coverage/rights decision and scoped canonical adapter with provenance,
explicit missingness, contract fixtures and a reproducible cohort. Keep V1's pinned
baseline separate; do not mix incompatible competitions/seasons silently.
Authentication, paid access and new data-rights decisions need explicit approval.

## 3. Entity resolution

Preserve namespaced provider IDs and existing player/team-season keys. Design a
separate cross-provider identity mapping with source evidence, confidence and
manual-review states. Names, accents, dates of birth and team labels may help
review but must not silently merge different players. Retain transfer spells.

Acceptance: audited mappings, ambiguous-case handling and reversible linkage;
no rewrite of canonical V1 IDs or guesses about unresolved personal fields.
This becomes necessary when a second provider is selected.

## 4. Deployment

Choose a target only after code/data rights and public analytical presentation
are approved. Define authentication, request limits, cache/storage boundaries,
snapshot verification, backups, restore, monitoring, dependency updates and cost.
The current loopback boundary is not a production deployment design.

Acceptance: a deployment plan and verified staging build with rollback and security
checks. External publication/deployment remains a separate authorized action.

## 5. UI/UX improvements

Observe real analyst tasks using the four working views. Prioritize clearer
eligibility/unavailable explanations, benchmark disclosure, keyboard/accessibility
support, navigation and presentation of evidence limits. Keep provenance and
activity-versus-quality distinctions visible. Preserve engine/API parity.

Acceptance: a small, user-tested workflow improvement without altering analytical
definitions or inventing data. Production polish follows actual usage needs.

## 6. Future LLM natural-language scouting interface

Only after stable contracts and validated task scope, translate natural-language
requests into explicit supported query/requirement structures. Show and validate
filters/weights, retrieve verified artifacts and cite provenance. Unsupported age,
market, contract or tactical claims must remain unavailable. Never let a language
model invent statistics, player identities, sources or scouting conclusions.

Acceptance: a bounded prototype and evaluation set for request interpretation,
unsupported queries, evidence faithfulness and deterministic-engine delegation.
Model credentials, personal-data routing, cost and external-model access need a
separate decision. No LLM dependency or integration is part of final V1.
