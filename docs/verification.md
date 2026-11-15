# Verification checkpoint — 15 November 2026

## Executed

- `python -m pytest -q --tb=short`: **37 passed**. Includes isolated PostgreSQL 16 integration, integrity and parent-update checks, three-role permissions, authentication, reversible migrations, analytical denominators, source checksums, idempotent imports, retained rejection evidence, domain rollback on database failure, and eight-page checks with empty and populated test data.
- `ruff check .` and `ruff format .`: lint and formatting checks run on the implementation.
- `python -m var_analytics.cli migrate`: applied all five forward migrations to the local application database.
- `python -m var_analytics.cli import-demo`: successful batch 1 with 2,189 preserved source observations. Repeated command returned `already_loaded` for batch 1.
- Local application data: **64 matches, 32 teams, 29 named referees (63 appointments), 829 players, 3,244 roster memberships, 1,953 mapped events and 228 event-tagged cards**. Referee materialized summary refreshed by owner maintenance.
- `python scripts/verify_demo.py`: HTTP health endpoint returned `ok`; root page and all eight pages ran against the populated application database without application exceptions/errors. This is a read-only application smoke check using Streamlit AppTest, not a browser screenshot review.

The ETL tests run only against `var_analytics_test`; their cleanup explicitly asserts that database name. Test-only invalid copies remain outside the application demo database. Tests verify that app_admin cannot edit lookup vocabularies or call the privileged validation function directly.

## Remaining limits

- The source does not provide verified VAR outcomes, AVAR appointments, review durations or announced added time. Those pages explain missing coverage rather than create observations.
- Data Management login exists; protected CSV previews/uploads and manual edits remain pending.
- Docker PostgreSQL services are running. The application currently runs from the local Python 3.11 environment; the application image and a fresh full Compose deployment have not been validated.
- Browser visual review remains pending. Automated page execution does not establish desktop/mobile appearance or keyboard usability.
- The importer is scoped to the documented World Cup 2022 snapshot. Failed/pending identical batches require review; automated retry/recovery and multi-provider reconciliation are not implemented.

Source files and secrets stay local. GitHub contains the implementation, schema, tests, attribution logo and reproducible download/import instructions.
