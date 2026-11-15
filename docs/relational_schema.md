# Proposed relational schema

Approval draft, not executable DDL. PostgreSQL 16 and 3NF are required. Physical identifiers will be unquoted lowercase versions of the blueprint names. All 20 blueprint tables remain; one supporting table is proposed explicitly below.

## Conventions and normalization

`PK` means primary key, `FK` foreign key, and `UQ` a unique constraint. Entity identifiers use UUIDs; provenance identifiers use bigint identity columns. Lookup codes use text primary keys. Names are not identifiers and will not be used to silently merge people or clubs.

Imported entity UUIDs will be deterministic from a fixed project namespace, stable provider code, entity kind and stable external key. This is a technical identity, not a fabricated football fact. A documented mapping version and preserved raw keys make repeat imports reproducible. Missing reliable identity causes a record to be quarantined for review. Source-specific identities are retained; combining providers requires an explicit reconciliation policy. Initially use one primary provider per competition/season to avoid double-counting the same match.

All imported operational tables additionally have a required `source_record_id bigint FK SOURCE_RECORD`. Curated lookup tables may omit that FK when their values are documented project vocabulary rather than provider observations. Administrative corrections must retain their evidence and an import/change batch identifying their origin; administrator access does not authorize invented missing facts. UUID identity generation applies to imported domain entities; new administrative entries use separately documented stable identities.

Raw payloads belong in SOURCE_RECORD JSONB, not operational columns. Arrays of teams, appointments or cards are represented as related rows. League is derived from season, player team is stored per match rather than as a mutable current-club attribute, and a card's team is derived from MATCH_PLAYER. These choices prevent historical and transitive-dependency errors.

## Required operational tables

| Table | Proposed attributes and keys | Main rules |
|---|---|---|
| COUNTRY | `country_id uuid PK`, `name text`, `iso_code text nullable UQ` | Do not guess missing ISO codes; names alone need not be unique |
| LEAGUE | `league_id uuid PK`, `country_id uuid nullable FK COUNTRY`, `name text`, `competition_kind text` | International competitions may have no single country |
| SEASON | `season_id uuid PK`, `league_id uuid FK LEAGUE`, `label text`, `starts_on date nullable`, `ends_on date nullable`; UQ `(league_id, label)` | Dates ordered when both known; no duplicated league_id in FOOTBALL_MATCH |
| TEAM | `team_id uuid PK`, `country_id uuid nullable FK COUNTRY`, `name text` | Source identifiers distinguish same-named teams |
| VENUE | `venue_id uuid PK`, `country_id uuid nullable FK COUNTRY`, `name text`, `city text nullable` | Unknown venue stays null in a match |
| REFEREE | `referee_id uuid PK`, `country_id uuid nullable FK COUNTRY`, `name text` | No guessed AVAR/referee names |
| OFFICIAL_ROLE | `role_code text PK`, `label text`, `var_eligible boolean` | Includes MAIN_REFEREE, ASSISTANT_1, ASSISTANT_2, FOURTH_OFFICIAL, VAR, AVAR |
| FOOTBALL_MATCH | `match_id uuid PK`, `season_id uuid FK SEASON`, `venue_id uuid nullable FK VENUE`, `home_team_id uuid FK TEAM`, `away_team_id uuid FK TEAM`, `kickoff_at timestamptz nullable`, `status text`, `home_score smallint nullable`, `away_score smallint nullable`, `home_shootout_score smallint nullable`, `away_shootout_score smallint nullable` | Different teams; nonnegative known scores; score pairs both known or both null; completed matches require home/away scores; shootout scores separate from match score |
| MATCH_OFFICIAL | PK `(match_id uuid FK FOOTBALL_MATCH, role_code text FK OFFICIAL_ROLE, slot_no smallint)`, `referee_id uuid FK REFEREE` | Positive slot; at most one MAIN_REFEREE per match; role slots support multiple source-recorded AVARs |
| DECISION_TYPE | `decision_type_code text PK`, `label text` | Includes source-supported goals, penalties, fouls and other mapped decisions; mapping documented |
| DECISION_OUTCOME | `outcome_code text PK`, `label text`, `outcome_scope text` | Scope distinguishes decision results from VAR review outcomes; explicit known upheld/overturned codes are separate |
| DECISION | `decision_id uuid PK`, `match_id uuid FK FOOTBALL_MATCH`, `decision_type_code text FK DECISION_TYPE`, `outcome_code text nullable FK DECISION_OUTCOME`, clock fields, `official_role_code text nullable`, `official_slot_no smallint nullable`, `description text nullable` | Composite FK `(match_id, official_role_code, official_slot_no)` to MATCH_OFFICIAL; role/slot either both null or both present; absent attribution is unavailable |
| DECISION_TEAM | PK `(decision_id uuid FK DECISION, team_id uuid FK TEAM)`, `involvement_code text` | Trigger verifies the team participates in the decision's match; involvement is only classified when source evidence supports it |
| VAR_INVOLVEMENT | `var_involvement_id uuid PK`, `decision_id uuid FK DECISION`, `review_kind text`, `outcome_code text nullable FK DECISION_OUTCOME`, `official_role_code text nullable FK OFFICIAL_ROLE`, `official_slot_no smallint nullable`, `duration_seconds numeric nullable`, optional clock fields, `description text nullable` | A decision can have multiple checks/reviews; nonnegative known duration; paired attribution; trigger derives the match from DECISION and verifies a VAR-eligible appointment in that match |
| PLAYER | `player_id uuid PK`, `country_id uuid nullable FK COUNTRY`, `name text`, `date_of_birth date nullable` | No current team column that would corrupt historical records |
| CARD_ISSUED | `card_id uuid PK`, `match_id uuid`, `player_id uuid`, `card_type text`, clock fields, `official_role_code text nullable`, `official_slot_no smallint nullable` | Composite FK `(match_id, player_id)` to MATCH_PLAYER; optional composite appointment FK; separate yellow, second-yellow dismissal and direct-red codes prevent ambiguous counts |
| ADDED_TIME | PK `(match_id uuid FK FOOTBALL_MATCH, period_code smallint)`, `announced_minutes integer`, `announced_seconds smallint nullable` | Periods 1-4 only; minutes nonnegative; known seconds 0-59; no row means no known announcement, not zero |

Clock fields are `period_code smallint`, `minute integer nullable`, `second smallint nullable`, `stoppage_minute integer nullable`, and `source_order integer nullable`. Known values must be valid and nonnegative; seconds must be 0-59. Preserve the source's clock convention in raw payloads and document conversion per adapter. Do not impose a universal 90-minute ceiling or turn unknown seconds into measured zero. A decision period is required; unknown event time remains nullable and is displayed separately in chronological views. Shootout events use their own period code and do not enter added-time averages.

Kickoff timestamps are timezone-aware only where the provider supplies a documented timezone. A date-only source must not be assigned a fabricated kickoff instant; it stays in raw data and is reported as incomplete until a date-only operational representation is approved. The expected candidate source timestamps will be audited before ingestion mappings are finalized.

The initial release records player cards; staff/bench-official disciplinary records must be classified as outside this table's scope and retained/reported, rather than assigned to fictitious players. Expansion requires an explicit schema proposal.

## Proposed supporting table

`MATCH_PLAYER(match_id uuid FK FOOTBALL_MATCH, player_id uuid FK PLAYER, team_id uuid FK TEAM, source_record_id bigint FK SOURCE_RECORD, PK(match_id, player_id))`.

This is an explicit addition to the blueprint's main-table list. It stores match-specific participation evidenced by a lineup or an explicit player/team relationship in a source event. A trigger verifies team_id is the home or away team. A card can then reference an actual player in that match through a composite FK, without storing redundant team_id on the card or relying on the player's current club. Where membership evidence is unavailable, retain the raw card and report it as pending validation instead of inventing membership.

## Required provenance tables

| Table | Proposed attributes and keys | Main rules |
|---|---|---|
| DATA_SOURCE | `data_source_id bigint PK`, `source_code text UQ`, `name text`, `reference_url text`, `license_reference text nullable`, `attribution_text text nullable`, `source_kind text` | Stable provider identity; distinguish provider import and evidence-backed manual correction |
| IMPORT_BATCH | `import_batch_id bigint PK`, `data_source_id bigint FK DATA_SOURCE`, `input_fingerprint text`, `transform_version text`, `started_at timestamptz`, `finished_at timestamptz nullable`, `status text`, `extracted_count integer`, `accepted_count integer`, `rejected_count integer`, `error_summary text nullable`; UQ `(data_source_id, input_fingerprint, transform_version)` | Fingerprint includes requested scope and input checksums; counts nonnegative; explicit failure/retry state; no duplicate successful batch for identical input/mapping |
| SOURCE_RECORD | `source_record_id bigint PK`, `import_batch_id bigint FK IMPORT_BATCH`, `entity_kind text`, `external_key text nullable`, `record_locator text`, `payload_sha256 text`, `raw_payload jsonb`, `captured_at timestamptz`, `validation_status text`, `validation_errors jsonb nullable`; UQ `(import_batch_id, record_locator)` | Record locator identifies file/response plus JSON pointer or CSV row; raw payloads retained even for rejected records; external IDs retained without assuming they exist for all records |

SOURCE_RECORD stores immutable observations; operational rows point to the observation supporting their current values. Prior batch records remain available through provider identity, external key and locator. Database privileges/triggers protect raw-payload mutation and deletion. Validation status may change through controlled processing. Original input hashes refer to original bytes, not reserialized JSON. Logs and payloads must not store API keys or authorization headers.

## Database integrity enforcement

Use declarative PK/FK/UQ/NOT NULL/CHECK rules first. Use PL/pgSQL triggers only for cross-table rules that cannot be expressed declaratively. PostgreSQL CHECK expressions must not query other rows: see the [PostgreSQL 16 constraint documentation](https://www.postgresql.org/docs/16/ddl-constraints.html).

| Rule | Enforcement and required negative test |
|---|---|
| Team cannot play itself | FOOTBALL_MATCH CHECK |
| Attribution must reference the same match | Composite appointment FKs on decisions/cards; VAR trigger follows its decision |
| VAR attribution must use VAR/AVAR eligibility | Appointment existence and OFFICIAL_ROLE eligibility trigger |
| Player's team must participate | MATCH_PLAYER trigger and CARD_ISSUED composite FK |
| Decision team must participate | DECISION_TEAM trigger |
| Added seconds restricted to 0-59 | ADDED_TIME CHECK; separate null handling |
| Completed scores present | Status/score CHECK; incomplete completed records retained as rejected raw records |
| Cross-record updates cannot invalidate old data | Guard updates to match participants, MATCH_PLAYER membership, appointment keys/roles, role eligibility and decision match association; restricted deletes; test both child insert and parent update paths |
| Concurrent writes cannot bypass trigger rules | Triggers lock referenced match/assignment rows in documented order; test relevant concurrent changes |
| Outcome scopes consistent | Trigger validates DECISION versus VAR_INVOLVEMENT outcome vocabulary |

Default FK deletion policy is RESTRICT/NO ACTION for retained football and provenance records. No cascading erasure of import evidence. Permitted admin deletion is explicit and dependency-aware.

## Indexes and analytics objects

Index referencing FK columns and common query paths: SEASON league, FOOTBALL_MATCH season/kickoff and both team IDs, MATCH_OFFICIAL referee/match, DECISION match/type/clock, DECISION_TEAM team, VAR_INVOLVEMENT decision/outcome, MATCH_PLAYER player/team, CARD_ISSUED match/player/type, ADDED_TIME period/match, IMPORT_BATCH source/time and SOURCE_RECORD batch/external key. Retain PK/UQ indexes rather than duplicating them. Add a partial unique index for the main-referee assignment. Validate choices with EXPLAIN ANALYZE on the selected real dataset; do not claim performance before measuring.

Create `mv_referee_stat_summary` at grain `(referee_id, season_id)`, with a unique index on that pair. Aggregate appointments, decisions, cards and reviews independently before joining to avoid multiplying counts. Match responsibility statistics use MAIN_REFEREE appointments; event-specific attribution is reported separately. Show matches, decisions, penalties, cards, checks/reviews, known outcomes and overturned outcomes only where covered. Expose refresh timestamp and coverage/sample counts.

Overturn rate = recorded overturned review outcomes / recorded known eligible review outcomes. Unknown outcomes are excluded and counted separately. The exact check-versus-review eligibility set will be documented after source auditing. Zero denominator returns unavailable. Duration means exclude unknown durations and show measured n. Added-time averages use announced values only. Second-yellow dismissal and red-card reporting must state their counting conventions.

Use ordinary views plus SQL joins, CTEs, aggregates and window functions for match timelines, rankings and comparisons. Refresh is an owner maintenance action: [PostgreSQL 16 requires materialized-view ownership to refresh](https://www.postgresql.org/docs/16/sql-refreshmaterializedview.html). Neither application role receives ownership or an unrestricted owner-role membership.
