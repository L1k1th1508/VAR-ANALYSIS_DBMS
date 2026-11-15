# Proposed ER diagram

Approval draft based on blueprint sections 5 and 9. All 20 required tables are retained. `MATCH_PLAYER` is one proposed supporting table for historically correct card/player/team validation. No SQL has been applied.

```mermaid
erDiagram
    COUNTRY o|--o{ LEAGUE : locates
    COUNTRY o|--o{ TEAM : associates
    COUNTRY o|--o{ VENUE : locates
    COUNTRY o|--o{ REFEREE : associates
    COUNTRY o|--o{ PLAYER : associates
    LEAGUE ||--o{ SEASON : contains
    SEASON ||--o{ FOOTBALL_MATCH : contains
    VENUE o|--o{ FOOTBALL_MATCH : hosts
    TEAM ||--o{ FOOTBALL_MATCH : home_team
    TEAM ||--o{ FOOTBALL_MATCH : away_team
    FOOTBALL_MATCH ||--o{ MATCH_OFFICIAL : assigns
    REFEREE ||--o{ MATCH_OFFICIAL : serves
    OFFICIAL_ROLE ||--o{ MATCH_OFFICIAL : defines
    FOOTBALL_MATCH ||--o{ DECISION : records
    MATCH_OFFICIAL o|--o{ DECISION : attributes_when_known
    DECISION_TYPE ||--o{ DECISION : classifies
    DECISION_OUTCOME o|--o{ DECISION : records_result
    DECISION ||--o{ DECISION_TEAM : involves
    TEAM ||--o{ DECISION_TEAM : participates
    DECISION ||--o{ VAR_INVOLVEMENT : reviewed_or_checked
    DECISION_OUTCOME o|--o{ VAR_INVOLVEMENT : records_review_result
    MATCH_OFFICIAL o|--o{ VAR_INVOLVEMENT : handles_when_known
    FOOTBALL_MATCH ||--o{ MATCH_PLAYER : records_participation
    PLAYER ||--o{ MATCH_PLAYER : participates
    TEAM ||--o{ MATCH_PLAYER : represents
    MATCH_PLAYER ||--o{ CARD_ISSUED : receives
    MATCH_OFFICIAL o|--o{ CARD_ISSUED : issues_when_known
    FOOTBALL_MATCH ||--o{ ADDED_TIME : announces
    DATA_SOURCE ||--o{ IMPORT_BATCH : provides
    IMPORT_BATCH ||--o{ SOURCE_RECORD : retains

    FOOTBALL_MATCH {
        uuid match_id PK
        uuid season_id FK
        uuid home_team_id FK
        uuid away_team_id FK
        uuid venue_id FK
        bigint source_record_id FK
    }
    MATCH_OFFICIAL {
        uuid match_id PK,FK
        text role_code PK,FK
        smallint slot_no PK
        uuid referee_id FK
    }
    MATCH_PLAYER {
        uuid match_id PK,FK
        uuid player_id PK,FK
        uuid team_id FK
        bigint source_record_id FK
    }
    DECISION {
        uuid decision_id PK
        uuid match_id FK
        text decision_type_code FK
        text outcome_code FK
        text official_role_code FK
        smallint official_slot_no
    }
    DECISION_TEAM {
        uuid decision_id PK,FK
        uuid team_id PK,FK
        text involvement_code
    }
    VAR_INVOLVEMENT {
        uuid var_involvement_id PK
        uuid decision_id FK
        text review_kind
        text outcome_code FK
        numeric duration_seconds
    }
    CARD_ISSUED {
        uuid card_id PK
        uuid match_id FK
        uuid player_id FK
        text card_type
    }
    ADDED_TIME {
        uuid match_id PK,FK
        smallint period_code PK
        integer announced_minutes
        smallint announced_seconds
    }
    DATA_SOURCE {
        bigint data_source_id PK
        text source_code UK
    }
    IMPORT_BATCH {
        bigint import_batch_id PK
        bigint data_source_id FK
        text input_fingerprint
    }
    SOURCE_RECORD {
        bigint source_record_id PK
        bigint import_batch_id FK
        text entity_kind
        text external_key
        jsonb raw_payload
    }
```

Country associations are optional where the source does not identify a country or a competition is international; the diagram's country edges describe the referenced relationship when present. A venue and recorded decision/review outcomes can also be unknown.

For readability, provenance edges to every operational table are omitted. Each imported operational row references the source record supporting its current version; `SOURCE_RECORD -> IMPORT_BATCH -> DATA_SOURCE` supplies the lineage. Raw records from prior batches remain retained. Exact source identity and raw locators allow earlier versions to be traced without duplicating provider fields throughout the schema.

The materialized view `mv_referee_stat_summary` derives statistics from matches, seasons, appointments, decisions, reviews and cards. It is a derived object rather than a separate entity. See the relational schema for composite keys, nullable attribution, trigger-enforced relationships and identity rules.
