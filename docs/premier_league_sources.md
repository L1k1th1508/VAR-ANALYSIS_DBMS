# Premier League dataset assessment

Checked 15 November 2026. This is source research, not an import. No account, subscription or Premier League database records were created.

## Findings

| Source | Verified scope / access | Project fit | Main gap |
|---|---|---|---|
| [StatsBomb Open Data](https://github.com/hudl/open-data) | At the pinned project revision: 380 matches in 2015/16; 38 in 2003/04 | Strongest immediate historical candidate; existing provider format | Predates VAR; no verified announcement or review-duration source |
| [Football-Data.co.uk](https://football-data.co.uk/englandm.php) | Season CSVs, including 2024/25; publisher describes match statistics and referees | Scores, appointments, aggregate team statistics | Aggregates do not identify individual cards/decisions; restrictive usage notice |
| [Sportmonks](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes/events) | Documentation includes VAR event sequences and outcomes | Promising VAR-era candidate, subject to plan coverage and real samples | No actual Premier League API response audited; announcement semantics need confirmation |
| [API-Football](https://www.api-football.com/documentation_v3) | Documentation lists VAR goal cancellation and penalty confirmation | Alternative event source | Labels alone do not establish every original/revised decision; no authenticated sample audited |
| [Premier League Match Centre](https://www.premierleague.com/en/news/4251195) | Official explanations of selected calls and subsequent video decisions | Small manually cited supplement | Editorial coverage, not a complete downloadable event dataset |

## Recommended next source

For **free historical match/referee analytics**, investigate StatsBomb 2015/16 first. Its match JSON was retrieved and parsed at the project's pinned revision:

| Season | Competition / season IDs | Match rows | Rows with a named referee |
|---|---|---:|---:|
| 2015/16 | `2 / 27` | 380 | 380 |
| 2003/04 | `2 / 44` | 38 | 4 |

Direct pinned sources:

- [Competition catalog](https://raw.githubusercontent.com/hudl/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/competitions.json)
- [2015/16 match JSON](https://raw.githubusercontent.com/hudl/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/matches/2/27.json)
- [2003/04 match JSON](https://raw.githubusercontent.com/hudl/open-data/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/matches/2/44.json)

Only the match inventory was checked; all season event/lineup files have **not** been downloaded or validated. The 2003/04 subset must not be represented as a full season. Follow StatsBomb's [attribution instructions](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/README.md) and [license](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf); public access is not blanket permission to redistribute provider files.

Both seasons predate Premier League VAR, introduced in [2019/20](https://www.premierleague.com/en/news/1747764). Historical scopes should distinguish “VAR not in use” from missing VAR data in a later season.

For **VAR-era analysis**, evaluate an authenticated Sportmonks sample for a completed season such as 2024/25, with API-Football as an alternative. This is a recommendation to validate samples, not a claim that either covers every blueprint field.

## Source-specific constraints

### Football-Data.co.uk

The [England downloads](https://football-data.co.uk/englandm.php) include the [2024/25 Premier League CSV](https://www.football-data.co.uk/mmz4281/2425/E0.csv). The [publisher's description](https://football-data.co.uk/data.php) lists scores, cards, fouls, shots and referees. These pages were checked; the CSV itself was not downloaded/audited in this assessment.

The data page limits intended use to private individuals and excludes commercial or data-training products using automated bots/scrapers/AI. Treat it as a restricted candidate, not an openly licensed feed for automated ingestion or redistribution. Confirm the intended project's permitted use with the publisher before adopting it.

Aggregate card/foul counts must not be expanded into invented CARD_ISSUED or DECISION rows. A separate aggregate-statistics design would need blueprint/schema review before implementation.

### Sportmonks

The [event guide](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes/events) describes VAR-related goals, cards and penalty outcomes. The [type reference](https://docs.sportmonks.com/v3/definitions/types/events) distinguishes event types from subtypes. Reconcile event chains into reviews rather than counting each status update separately; validate the current type catalog and real responses before mapping outcomes.

The [period guide](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes/periods) contains `time_added`, separate from event `extra_minute`. The reviewed documentation did not explicitly establish that the retained value always equals the original board announcement. Confirm that meaning and historical completeness, then compare sample fixtures against independent announcement reports. Do not use elapsed injury time or coarse event-clock subtraction as measured review duration.

Access depends on the selected plan and [terms](https://www.sportmonks.com/terms-of-service/). Confirm storage, display and redistribution rights for the intended use. No trial or subscription was activated.

### API-Football

The [documentation](https://www.api-football.com/documentation_v3) includes VAR labels, but “penalty confirmed” needs context before classification as upheld or overturned. Verify the original on-field decision and event sequence. Event elapsed/extra fields are clocks, not proof of the minimum time announced for a half.

Confirm competition/season coverage and missing-field rates using authenticated responses. Review the [terms](https://www.api-football.com/terms), including limits on raw-data resale. No API key or sample response was used in this assessment.

### Official Premier League reports

The [2024/25 Match Centre update for matchweeks 21–25](https://www.premierleague.com/en/news/4251195) explains selected on-field calls and subsequent VAR action. These can substantiate individual cited facts, like the existing World Cup supplement, but do not supply a complete event feed, every official appointment, all announced periods or per-review timings. Aggregate KMI accuracy or average delay must not become individual outcomes/durations.

## Acceptance checks before a future import

1. Select a season and confirm access, storage, display and redistribution terms.
2. Pin the source version/capture time; preserve response hashes, URLs and import batches.
3. Audit match IDs, dates, teams, scores, referee identities, player/event links and duplicate status updates.
4. Measure coverage of original decisions, final outcomes, reviews versus checks, VAR/AVAR names, measured durations and announced minutes by period. Keep unsupported values unknown.
5. Add an explicit adapter/scope and tests. Current `extract.py` rejects competition/season IDs other than `43 / 106`; changing a manifest alone is not a supported import.
6. Preserve the World Cup demo and validate competition/season isolation and counts in the test database before application loading.

No single free, complete VAR-era Premier League dataset covering all blueprint fields was verified in this search.
