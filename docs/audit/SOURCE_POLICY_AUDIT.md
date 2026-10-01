# Phase 0 source and publication audit

Verified 30 September 2026 (Asia/Jakarta). Official sources only. Website/documentation verification is distinct from authenticated API payload verification: no account was created, no credentials requested or used, and no authenticated football-data.org payload was tested in this audit.

## football-data.org

### Published free-plan contract

The pricing page lists €0/month, 12 competitions, delayed scores and schedules, fixtures, league tables, and 10 calls/minute. Squads, lineups/substitutions, scorers and cards appear in the paid Free + Deep Data offer rather than the free feature list. Treat these as unavailable to the proposed free-only V1 unless an authenticated test proves otherwise. Live scores and 10 seasons of history are separate paid features. [Official pricing](https://www.football-data.org/pricing)

The coverage page names the following 12 free competitions. The codes and numeric IDs are separately verified against the official lookup table; this is documentation evidence, not a statement that every historical season is free. [Coverage](https://www.football-data.org/coverage), [Lookup table](https://docs.football-data.org/general/v4/lookup_tables.html)

| Competition | Code | ID |
|---|---|---:|
| UEFA Champions League | CL | 2001 |
| Primeira Liga, Portugal | PPL | 2017 |
| Premier League, England | PL | 2021 |
| Eredivisie, Netherlands | DED | 2003 |
| Bundesliga, Germany | BL1 | 2002 |
| Ligue 1, France | FL1 | 2015 |
| Serie A, Italy | SA | 2019 |
| La Liga / Primera Division, Spain | PD | 2014 |
| Championship, England | ELC | 2016 |
| Campeonato Brasileiro Série A, Brazil | BSA | 2013 |
| FIFA World Cup | WC | 2000 |
| European Championship | EC | 2018 |

### API contract and verification boundary

Use HTTPS base `https://api.football-data.org/v4`. Registration supplies a token used in `X-Auth-Token`. The published policy allows anonymous clients 100 requests per 24 hours, limited to area and competition lists. Free authenticated clients have 10 requests/minute. The policy page's paid-plan rate counts disagree with current pricing; use the account's actual entitlement for any future paid plan. [Policies](https://docs.football-data.org/general/v4/policies.html), [Registration](https://www.football-data.org/client/register)

Official v4 routes relevant to an adapter are below. Route existence is not proof of free access to its entire response. [Quickstart route catalogue](https://www.football-data.org/documentation/quickstart)

| Documented route | Purpose | V1 treatment |
|---|---|---|
| `GET /competitions` | Competition list | Anonymous discovery; authenticate to discover account coverage |
| `GET /competitions/{code}` | Competition and seasons | Check actual historical entitlement |
| `GET /competitions/{code}/standings` | Standings | Core contextual source, when supported by competition type |
| `GET /competitions/{code}/matches` | Competition matches | Core fixtures/results source |
| `GET /competitions/{code}/teams` | Teams | Contextual identities; test squad field entitlement |
| `GET /teams/{id}` | Team details | Do not promise squad/contract fields on free tier |
| `GET /teams/{id}/matches` | Team matches | Contextual results, account coverage applies |
| `GET /matches`, `/matches/{id}` | Matches | Results/context, deeper fields depend on entitlement |
| `GET /competitions/{code}/scorers` | Top scorers | Optional only after entitlement verification |
| `GET /persons/{id}`, `/persons/{id}/matches` | Person and appearances | No free-tier recruitment dependency |

The competition resource documents that authenticated competition lists are filtered to the client; unauthenticated lists show all available competitions. It also warns that standings are unavailable for CUP and PLAYOFFS and that historical deducted points may be removed. [Competition reference](https://docs.football-data.org/general/v4/competition.html)

The reference examples show person identity, position, birth date and nationality, and team examples show contracts and market values. These examples are schema illustrations, often dated 2021–2022; they do not verify today's values, completeness or free access. [Person reference](https://docs.football-data.org/general/v4/person.html), [Team reference](https://docs.football-data.org/general/v4/team.html)

Null values and empty lists are explicitly valid. Date-sensitive defaults use UTC; match lists fold deeper information by default, with unfolding headers for lineups, bookings, substitutions and goals. This is response-shape control, not a way to bypass plan permissions. [Policies](https://docs.football-data.org/general/v4/policies.html)

The response headers `X-RequestCounter-Reset` and `X-RequestsAvailable` expose throttle state. Implementation recommendation (inference): use a shared limiter, cache immutable responses, respect reset information, and do not convert an empty restricted payload into zero player performance. [Header reference](https://docs.football-data.org/general/v4/lookup_tables.html)

### Attribution, secrets and graphics

Registration terms require visible attribution: “Football data provided by the Football-Data.org API”. They also prohibit storing developer credentials in open-source repositories. Team logos and profile photos remain copyrighted by their owners and require separate consent; an API URL does not grant graphic rights. The published terms display an effective/update date of June 1, 2018 despite being available today. [Official terms, sections 6, 7 and 9](https://www.football-data.org/client/register)

Implementation recommendation (inference): store the token in an environment variable, redact it in logs, publish code/config examples only, and use text names or neutral shapes instead of unlicensed crests. The reviewed terms do not establish an explicit broad raw-data redistribution licence; do not infer one from free API access.

### Fitness for recruitment V1

Decision (inference from the verified feature contract): useful as a context adapter for teams, competitions, match outcomes and standings. It is not a defensible primary free source for player event analytics, xG, progressive actions, pressures, spatial role fit, contracts or valuations. Recruitment rankings should be based on event data actually observed in the selected StatsBomb cohort, with football-data.org kept optional and honestly capability-labelled.

## StatsBomb Open Data

The official README describes JSON competition/seasons, matches, events, lineups and selected-match 360 files. It requires StatsBomb source acknowledgement and logo when sharing analysis. The old `statsbomb/open-data` GitHub URL currently redirects to `hudl/open-data`; the README still uses the StatsBomb brand. [README](https://raw.githubusercontent.com/statsbomb/open-data/master/README.md), [Repository](https://github.com/hudl/open-data)

The PDF licence was downloaded and text-extracted from the official repository, pinned to commit `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`. It identifies itself as the StatsBomb Public Data User Agreement, last updated 8 September 2023. [Pinned official licence](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf)

Verified licence restrictions and conditions:

- Sections 1.1 and the introduction permit research/analysis and public sharing of resulting conclusions.
- Section 1.2.1 prohibits editing/distorting, distributing, reproducing, selling or providing the data to external/third parties.
- Section 1.2.2 prohibits commercial exploitation of either the data or analysis derived from it.
- Section 1.4 requires the StatsBomb brand logo on published analysis.
- Section 7 preserves StatsBomb's data ownership and restricts further exploitation absent express prior written consent, except where expressly permitted.
- Section 2 asks users to provide name/email through the resource centre before access; this audit did not register the user.
- Sections 2–3 reserve withdrawal and provide data as-is, without accuracy/completeness warranties.

Each item above is a paraphrase of the [official licence](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf), not a standard permissive open-source licence claim.

Implementation/publication decision (inference): build a noncommercial research/portfolio tool, publish source code and derived analysis with required credit/logo, and provide a downloader that fetches directly from the official repository. Keep raw JSON, cached provider payloads and database extracts out of the public repository and downloadable app exports. Do not treat a deployment serving raw data or commercial recruitment service as automatically permitted. Obtain explicit provider permission before commercial use or redistribution. A public CSV of event rows is data redistribution, even if generated locally; a derived player analytical report is a different output, but must remain noncommercial and attributed.

## Remaining checks before claiming live integration

1. With a user-provided token, verify free account competition list and representative PL teams, team detail, scorers, persons and matches payloads; record HTTP status, fetched time, fields actually present, and account permissions without logging the token.
2. Select the StatsBomb competition/season from its actual catalogue, inspect match count and completeness, and pin a repository commit for reproducibility.
3. Verify logo/media-pack availability before any public analysis release; public outputs need the StatsBomb logo as well as textual attribution.
4. Record per-source ID namespaces; never equate football-data and StatsBomb IDs or join players solely on a name.

These are verification tasks and design recommendations, not completed integration claims.
