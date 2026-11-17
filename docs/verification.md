# Verification checkpoint — 15 November 2026

## Data Management — 17 November 2026

- Implemented `admin_service.py` and native Streamlit management forms for 15 operational record types. No schema migration or production record mutation was required to enable the feature.
- Administrator capability/expiry and the PostgreSQL `app_admin` role are checked independently. Lookup vocabularies, metadata, permissions and owner maintenance are outside the editor's table allowlist.
- CSV previews use Pandas/Pydantic, UTF-8 parsing, a 2,000,000-byte/500-row limit, exact columns, typed fields and duplicate-key checks. Imports insert new records atomically; conflicts do not silently overwrite provider data.
- Manual additions/edits/deletions retain citation, reason, submitted fields, before-image and session ID in immutable raw evidence. Failed saves preserve rejected evidence while rolling back domain changes. Deletions require exact-row confirmation, optimistic edit checks and database FK permission; there is no cascade-delete control.
- `python -m pytest tests/test_admin.py -q --tb=short`: **14 passed in 43.06s**. Covers direct API authorization, wrong database role, CRUD/audit preservation, stale edits, duplicate prevention, malformed CSV, rollback, FK protection, clock ranges and expired sessions.
- `python -m pytest tests/test_admin.py tests/test_ui.py -q --tb=short`: **24 passed in 53.29s** at the UI checkpoint, including authenticated form creation, search, disabled delete controls, CSV upload-widget presence, sign-in/out and all eight empty pages.
- Read-only authenticated AppTest smoke against the running local database: all **15 record types** rendered Browse/Edit and Add forms; CSV controls rendered. No Save/Import/Delete actions were submitted against demo data. Referee materialized-summary refresh remains owner maintenance.
- Browser appearance and OS file-dialog interaction remain outside AppTest coverage. CSV parsing/import and atomic rejection are tested directly at the service boundary.
- Final `python -m pytest -q --tb=short`: **69 passed in 299.77s**. `ruff check .` and `ruff format --check .` passed. Production mutation buttons were not submitted during verification.

## Premier League 2015/16 announcements — 16 November 2026

- User-selected scope: announcements for the existing historical season; VAR remains not applicable.
- `python -m var_analytics.cli import-premier-added-time`: successful batch 5 with three cited source observations and three announcement rows. No matches, decisions, cards or VAR rows created. Repetition returned `already_loaded`.
- Verified periods: Arsenal–Leicester first half 2 minutes, second half 4 minutes; Chelsea–Tottenham second half 6 minutes. First-half sample n=1; second-half n=2. Missing periods/seconds remain unknown.
- `python -m pytest tests/test_premier_added_time.py tests/test_supplements.py -q --tb=short`: **14 passed in 81.46s**. Checks include exact match/season reconciliation, retained failure evidence, rejection of VAR in the historical announcement importer, idempotency, existing decision preservation, aggregate means, provenance links and page behavior.
- `python scripts/verify_demo.py --with-premier-league --with-premier-added-time`: HTTP health, preserved World Cup and historical Premier League counts, the three announcements and all eight pages passed. This uses AppTest, not browser visual review.
- Final suite for the selected scope: `python -m pytest -q --tb=short --ignore=tests/test_premier_evidence.py`: **54 passed in 245.83s**. The ignored provisional VAR-era test file was subsequently removed from the source tree when the user selected the historical-only scope; the final tree contains these 54 tests. Lint, formatting, documentation links and staged privacy checks passed.

## Premier League extension — 16 November 2026

- `python scripts/fetch_demo.py --dataset premier-league`: downloaded 763 checksummed files at the existing pinned provider revision.
- `python -m var_analytics.cli import-premier-league`: successful batch 3, 11,888 retained observations. Added 380 matches, 20 clubs, 19 referees with 380 appointments, 644 players, 13,678 roster memberships, 10,555 decision events and 1,262 event-tagged cards.
- This is Premier League 2015/16. VAR was not in use; announced added time and measured review durations are unavailable. No synthetic records or schema changes were introduced. World Cup evidence remains attached to its original matches.
- `python -m pytest tests/test_etl.py -q --tb=short`: **8 passed in 633.10s**. Includes full-season mapping, explicit scope rejection, coexistence with World Cup data, idempotency, unchanged existing decision provenance, materialized-summary totals and dashboard filter/empty-state checks. Source extraction was unusually slow on this run; the season fixture is now shared within the test module to avoid repeated reads.
- `python scripts/verify_demo.py --with-premier-league`: passed HTTP health, Premier League counts and sidebar selection, preserved World Cup counts, and all eight application pages. Combined match count is 444. Visual browser review remains pending.
- Repeating `import-premier-league` returned `already_loaded` for batch 3. Lint, formatting, documentation links and staged privacy checks passed; no raw provider data or configured credentials are included in Git.
- `python -m pytest -q --tb=short --ignore=tests/test_etl.py`: **41 passed in 143.99s**. Together with the eight ETL tests above, all **49 tests passed** across two non-overlapping runs.

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
- Data Management previews/imports/add/edit/confirmed-delete workflows are implemented; see the 17 November checkpoint and [usage guide](data_management.md).
- Docker PostgreSQL services are running. The application currently runs from the local Python 3.11 environment; the application image and a fresh full Compose deployment have not been validated.
- Browser visual review remains pending: the browser access host was unavailable and Windows computer use was not approved to access Brave. Automated page execution does not establish desktop/mobile appearance or keyboard usability.
- The importers are scoped to the documented World Cup 2022 snapshot and cited supplement. Exact supplemental match/event reconciliation is tested. Failed/pending identical batches require review; automated retry/recovery and general multi-provider reconciliation are not implemented.

Source files and secrets stay local. GitHub contains the implementation, schema, tests, attribution logo and reproducible download/import instructions.
