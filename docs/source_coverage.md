# Local demonstration source and field coverage

The user requested a populated local dashboard after initially deferring ingestion for a fuller licensed source. The local demo now uses real StatsBomb Open Data for all 64 FIFA World Cup 2022 matches. This is a limited source adapter; a fuller licensed source is still required for the unavailable VAR and added-time fields. No synthetic football records are used.

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

## Other candidate and source boundaries

[API-Football documentation](https://www.api-football.com/documentation-v3) describes VAR goal-cancelled and penalty-confirmed event labels. Its event elapsed/extra clocks are not evidence of announced added time or measured VAR review duration. No authenticated competition-specific response was obtained, and no API-Football adapter is selected. [Provider terms](https://www.api-football.com/terms) and actual field coverage need review before a future import. No paid account or subscription was created.

StatsBomb's [repository guidance](https://github.com/hudl/open-data) requires attribution for shared analyses, including its logo. See the [pinned license](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf) for permitted use. This delivery preloads the user's local research database; it does not publish raw provider files.
