# Verification checkpoint — 15 November 2026

## Executed

- `python -m pytest -q --tb=short`: **46 passed in 99.60s**. Includes isolated PostgreSQL 16 integration, integrity and parent-update checks, three-role permissions, authentication, reversible migrations, analytical denominators, source checksums, idempotent imports, retained rejection evidence, domain rollback on database failure, and eight-page checks with empty and populated test data. The nine added supplement tests cover exact match/event reconciliation, invalid annotations, unchanged penalty-shot counts, missing timing, per-period averages, date filters, rollback and populated VAR/added-time charts.
- `ruff check .` and `ruff format .`: lint and formatting checks run on the implementation.
- `python -m var_analytics.cli migrate`: applied all six forward migrations to the local application database. Migration 006 only adds two reviewed-claim vocabulary entries; no existing records were deleted.
- `python -m var_analytics.cli import-demo`: successful batch 1 with 2,189 preserved source observations. Repeated command returned `already_loaded` for batch 1.
- `python -m var_analytics.cli import-evidence`: successful batch 2 with **21 preserved factual annotations**, creating three reviewed-claim decisions, six VAR reviews and 15 announcement records. Repeat returned `already_loaded` for batch 2.
- Local application data: **64 matches, 32 teams, 29 named referees (63 appointments), 829 players, 3,244 roster memberships, 1,953 mapped provider events plus three reviewed claims (1,956 decisions), six VAR reviews, 15 announcement records and 228 event-tagged cards**. Referee materialized summary refreshed by owner maintenance.
- `python scripts/verify_demo.py`: HTTP health endpoint returned `ok`; root page and all eight pages ran against the populated application database without application exceptions/errors. This is a read-only application smoke check using Streamlit AppTest, not a browser screenshot review.

The ETL tests run only against `var_analytics_test`; their cleanup explicitly asserts that database name. Test-only invalid copies remain outside the application demo database. Tests verify that app_admin cannot edit lookup vocabularies or call the privileged validation function directly.

## Remaining limits

- The supplement covers selected cases only: six matches with VAR evidence and seven with announcements. VAR/AVAR appointments and measured review durations remain unavailable. No tournament-wide VAR rate or complete added-time coverage is claimed.
- Data Management login exists; protected CSV previews/uploads and manual edits remain pending.
- Docker PostgreSQL services are running. The application currently runs from the local Python 3.11 environment; the application image and a fresh full Compose deployment have not been validated.
- Browser visual review remains pending: the browser access host was unavailable and Windows computer use was not approved to access Brave. Automated page execution does not establish desktop/mobile appearance or keyboard usability.
- The importers are scoped to the documented World Cup 2022 snapshot and cited supplement. Exact supplemental match/event reconciliation is tested. Failed/pending identical batches require review; automated retry/recovery and general multi-provider reconciliation are not implemented.

Source files and secrets stay local. GitHub contains the implementation, schema, tests, attribution logo and reproducible download/import instructions.
