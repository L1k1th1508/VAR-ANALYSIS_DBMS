# Local demonstration source and field coverage

The local demo uses real StatsBomb Open Data for all 64 FIFA World Cup 2022 matches, supplemented by selected cited match facts for VAR and announced added time. The supplement is deliberately partial; it does not establish tournament-wide VAR rates. No synthetic football records are used.

## Reproducibility and provenance

- Provider: [StatsBomb Open Data](https://github.com/hudl/open-data).
- Pinned repository revision: `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`.
- Competition / season: `43 / 106`.
- `scripts/fetch_demo.py` downloads 131 files directly from the provider into ignored `data/raw/statsbomb` and writes `demo_manifest.json` with SHA-256 file checksums.
- `extract.py` verifies every consumed JSON file against that manifest. `transform_validate.py` validates records and relationships with Pydantic and Pandas. `load.py` records original JSONB observations, source locators, record hashes and batch results before transactional domain loading.
- Stable provider-derived UUIDs and a mapping-version/input-fingerprint constraint prevent duplicate imports. The import uses `app_admin`; materialized-view refresh uses the separate owner maintenance connection.
- Raw observations selected for this adapter comprise matches, team lineups and mapped events. Unmapped event types remain in the complete local source files; they are not counted as rejected records.
- Raw data and credentials are not committed, packaged in the image or redistributed through GitHub. The local PostgreSQL volume keeps the loaded demonstration available offline.

## Observed scope and mappings

| Data | Source and meaning | Coverage / limitation |
|---|---|---|
| Matches and scores | Match JSON `match_id`, `home_team`, `away_team`, `home_score`, `away_score` | 64 matches, 32 teams; scores exclude shootout tally, which is not inferred |
| Competition and season | Match JSON `competition`, `season` | FIFA World Cup, 2022 |
| Main referee | Match JSON `referee.id`, `referee.name` | 63 appointments, 29 distinct referees; one match has no named referee |
| Venue and country | Match `stadium` and explicitly supplied country IDs | 8 venues; no country ID invented for “International” |
| Match clock | `match_date`, `kick_off` | Stored as date and local clock; timezone and UTC instant remain null |
| Players and team membership | Team lineup `player_id`, `player_name`, `country` | 829 players, 3,244 match/player roster memberships; includes unused substitutes |
| Fouls | Event type `Foul Committed` | Includes recorded advantage; a provider event, not an independent correctness assessment |
| Goals | Shot `outcome.name = Goal`, or `Own Goal Against` | One event row; own-goal team involvement means the team recorded in that event |
| Penalties | Shot `type.name = Penalty`, periods 1–4 | Penalty shots, not a complete list of penalty awards. Scored penalties remain PENALTY rows with GOAL outcome, avoiding duplicate event rows |
| Decision totals | Union of the three mappings above | 1,953 distinct source events; shootout shots excluded |
| Cards | `foul_committed.card` or `bad_behaviour.card`, recorded player/team | 228 event-tagged cards. Lineup card summaries are not imported again. Yellow, second yellow and direct red remain distinct |
| Event chronology | `period`, `minute`, `second`, `index` | Preserve source clock and ordering; never reinterpret event duration as VAR duration |
| Direct official attribution | No explicit event-to-official identity | Null; aggregate referee statistics describe main-referee match responsibility |
| VAR checks, reviews, outcomes | No explicit verified coverage in this adapter | Unavailable; no inferred overturned/upheld outcomes |
| VAR / AVAR appointments | No named verified appointments | Unavailable |
| Review duration | No documented review timing | Unavailable |
| Announced added time | No announcement evidence | Unavailable; final event clocks are not announcements |

The import captures 2,189 original observations. Entity/table counts differ because a single source observation supports several normalized rows.

## Cited VAR and announcement supplement

`data/supplements/world_cup_2022_evidence.json` contains 21 manually verified factual annotations, each with a source URL and a location/context within that report. Sources are England Football, The Guardian, Sky Sports, FourFourTwo and AS. These facts supplement the provider limitations in the table above. Original articles, liveblogs and PDFs are not redistributed; their copyright remains with the publishers. The database hashes and preserves the annotation itself, not a claimed copy of the remote article.

- Six selected reviews across six matches: England–Iran, Denmark–Tunisia, Tunisia–France, Japan–Spain, Croatia–Belgium and England–France. Five reversed an initial decision; one retained it. This is a selection of documented cases, not a representative sample or complete list of VAR interventions/checks. The displayed 5/6 rate applies only to these cases.
- Three reviews link to existing provider events by exact event ID. Three additional parent decisions use GOAL_REVIEW or PENALTY_REVIEW categories, preserving the distinction from valid goals and penalty shots. Penalty-shot counts remain unchanged. The total decision count becomes 1,956.
- Fifteen announced-time observations across seven matches, including all four periods of Argentina–France. First-half coverage is six records; second-half coverage is seven. England–France has only its second-half announcement. Both extra-time periods have one observation each, from the final. Missing periods are absent, never zero-filled or used to imply complete match totals.
- Review clocks, review duration, VAR/AVAR identities and announcement seconds remain null. Reported incident minutes on newly created decisions are not copied to review-start times.
- Period averages use the reported minute component and expose the number of records and seconds coverage. The six first-half observations sum to 32 minutes; the seven second-half observations sum to 50 minutes. Extra-time announcements in the final are one and three minutes.

`supplements.py` validates the facts with Pydantic and Pandas, then checks exact match IDs, competition/season, dates, teams, scores and linked decision categories/periods against the existing database. It rejects conflicts with another announcement source. Import batches preserve evidence before validation; domain writes are atomic and deterministic. Repeating the same file is a no-op. The owner refreshes the referee materialized summary separately.

### Announcement semantics audit

FIFA full-time PDFs were evaluated locally with `scripts/audit_fifa_reports.py`. Their “Additional time” values do not consistently equal the original board announcement: for example, England–Iran shows 13 for the second half whereas the live report records an announcement of ten. These PDF values were **not imported** as announced minutes. The supplement uses explicit announcement reports, never the final event clock or elapsed stoppage time.

### Page design

Keep the existing white (#FFFFFF), ink (#18354A), blue (#236FA1), green (#236B5B), amber (#9A5A00) and red (#B23A48) palette, Source Sans body type and existing dashboard headings. Left-align the reading order: coverage → outcomes or period averages → match/category comparison → linked evidence. Horizontal match bars keep team names readable. Missing periods stay absent. Labels and tables convey the same distinctions as chart colors. The football-specific unit is a reviewed decision or announced period, rather than decorative scorecards or an unsupported performance ranking.

## Other candidate and source boundaries

### Premier League 2015/16 extension

Selected 2015/16 announced-time evidence now supplements the existing matches: three verified periods across Arsenal?Leicester and Chelsea?Tottenham. See [the source assessment](premier_league_sources.md#selected-201516-announced-time). All unverified periods remain unknown, and VAR is not applicable.

The same pinned StatsBomb revision supports competition/season `2 / 27`. Run `scripts/fetch_demo.py --dataset premier-league`, then `python -m var_analytics.cli import-premier-league`. The verified local import preserves 11,888 observations supporting 380 matches, 20 domestic clubs, 19 referees (380 main-referee appointments), 644 players, 13,678 match/player memberships, 10,555 mapped decision events and 1,262 event-tagged cards. These are per-season counts; shared entities such as players are not necessarily additive across datasets. Full events and lineups use the same mappings and integrity validation as the World Cup. Competition kind is domestic; source local clocks retain null timezone/UTC instant. The 763 checksummed source files stay ignored in a separate directory. Deterministic provider IDs preserve entity identity across seasons and prevent duplicate event rows. The application import succeeded as batch 3 on 16 November 2026.

The dashboard's league/season filters isolate each dataset; all-league counts combine them. Premier League VAR began in 2019/20, so 2015/16 has no applicable VAR activity. Only selected announced-time periods are verified. Existing World Cup review/announcement evidence remains linked only to World Cup matches. No schema changes or synthetic observations are required for this extension. See the [Premier League assessment](premier_league_sources.md).

[API-Football documentation](https://www.api-football.com/documentation-v3) describes VAR goal-cancelled and penalty-confirmed event labels. Its event elapsed/extra clocks are not evidence of announced added time or measured VAR review duration. No authenticated competition-specific response was obtained, and no API-Football adapter is selected. [Provider terms](https://www.api-football.com/terms) and actual field coverage need review before a future import. No paid account or subscription was created.

StatsBomb's [repository guidance](https://github.com/hudl/open-data) requires attribution for shared analyses, including its logo. See the [pinned license](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf) for permitted use. This delivery preloads the user's local research database; it does not publish raw provider files.
