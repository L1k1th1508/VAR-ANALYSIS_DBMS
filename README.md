# Referee & VAR Decision Analytics

An eight-page dashboard for football matches, referee assignments, decisions, VAR reviews and announced added time. Built with PostgreSQL 16, Python 3.11, SQLAlchemy 2.0, Pandas, Pydantic, Streamlit, Plotly, Docker Compose and Pytest.

The setup below downloads real World Cup 2022 data into your own local database. **No API key is needed.** The commands work in Windows PowerShell, macOS Terminal and Linux shells; `uv run` selects the project environment without OS-specific activation commands.

## What is included

| Page | Contents |
|---|---|
| Home Dashboard | Match, team, referee and decision totals |
| Match Explorer | Scores, appointments, event chronology and source evidence |
| Referee Analytics | Recorded match responsibilities, cards and penalty shots |
| VAR Analytics | Selected review outcomes, categories and source reports |
| Team Analytics | Recorded team involvement, cards and penalty shots |
| Added Time Analytics | Announced minutes by period and match, with citations |
| Data Management | Administrator sign-in; uploads/manual editing are not implemented yet |
| Data Quality and Methodology | Import history, validation, coverage and limitations |

The demo has **64 matches, 32 teams, 29 named referees, 1,956 decision rows and 228 event-tagged cards**. Decision rows comprise 1,953 provider events and three additional reviewed claims. A cited supplement adds **six selected VAR reviews and 15 announced-time records across seven matches**. VAR/added-time coverage is partial. Review durations and VAR/AVAR appointments remain unavailable; no synthetic football data is used.

## 1. Install prerequisites

- [Git](https://git-scm.com/downloads) to clone the repository.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) to install Python 3.11 and locked dependencies.
- [Docker Desktop](https://docs.docker.com/desktop/) on Windows/macOS, or Docker Engine with the [Compose plugin](https://docs.docker.com/compose/install/) on Linux. Start Docker before continuing. On Windows, use Linux containers and complete Docker Desktop's WSL 2/virtualization setup if requested.
- Internet access for the first dependency, Docker image and source-data downloads.

You do **not** need a separate PostgreSQL installation. This guide runs Streamlit locally and PostgreSQL 16 in Docker. A complete application-container deployment has not yet been validated.

Open a new terminal after installing the tools:

```sh
git --version
uv --version
docker version
docker compose version
```

`docker version` must show a working server, not just the client. Default local ports: **8501** for Streamlit, **55432** for the application database and **55433** for the optional test database. They bind to your own machine only.

## 2. Clone and prepare

Run commands in order, resolving any error before proceeding:

```sh
git clone https://github.com/L1k1th1508/VAR-ANALYSIS_DBMS.git
cd VAR-ANALYSIS_DBMS
uv python install 3.11
uv sync --frozen --python 3.11
uv run --frozen python scripts/setup_env.py
```

Keep subsequent commands in this repository folder. `--frozen` uses the committed `uv.lock`; the project requires Python 3.11.

The setup script creates private, Git-ignored files:

- `.env`: generated database credentials, connection URLs and application password hash.
- `.cache/initial-admin-password.txt`: the generated password for **Data Management**. Open this file locally when you need to sign in. Analytics pages need no login.

Do not copy `.env.example` to `.env` first: it contains placeholders. The script preserves an existing `.env` and exits without replacing it. Keep the original credentials on an existing installation; editing `.env` does not change passwords inside an initialized database. Never commit or share either private file.

## 3. Start PostgreSQL and create the schema

```sh
docker compose up -d --wait db
uv run --frozen python -m var_analytics.cli migrate
```

The first command waits for database health. Initialization creates `db_owner`, `app_reader` and `app_admin`; migrations create the normalized schema, constraints, triggers, views and permissions. Application sign-in is separate from database roles.

To inspect health without displaying credentials:

```sh
docker compose ps db
```

## 4. Download and load the demo

```sh
uv run --frozen python scripts/fetch_demo.py
uv run --frozen python -m var_analytics.cli import-demo
uv run --frozen python -m var_analytics.cli import-evidence
```

The download retrieves 131 files from a pinned StatsBomb revision into ignored `data/raw/statsbomb`. Allow several minutes depending on your connection. Import validates hashes and records and preserves provenance. Load the main demo **before** the supplement: the supplement reconciles against existing match/event IDs.

Successful imports print a result with `status` set to `success`. Repeating an identical successful import returns `already_loaded` without duplicating records. Failed/pending batches require inspection rather than silent retries. Each import refreshes the referee materialized summary through owner maintenance.

Provider files are downloaded directly, not redistributed here. Review [StatsBomb attribution guidance](https://github.com/hudl/open-data) and the [pinned license](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf). The included factual supplement contains citations, not source articles. See [field mappings and coverage](docs/source_coverage.md).

## 5. Launch the dashboard

```sh
uv run --frozen streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true
```

Open **[http://127.0.0.1:8501/](http://127.0.0.1:8501/)** on the same computer. Keep the terminal running. Use the sidebar to select a page and competition, season or date filters. With the full demo selected, Home should show 64 matches and six recorded VAR reviews.

After initial setup and loading, analytics work offline with the database running. External source links still require internet access.

## Stop and restart

Press **Ctrl+C** in the Streamlit terminal. Stop the database without losing its data:

```sh
docker compose stop db
```

For later use, run only:

```sh
docker compose up -d --wait db
uv run --frozen streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true
```

You do not need to regenerate credentials, download or reimport data. The `pgdata` Docker volume preserves it. **Do not run `docker compose down -v` or delete that volume for a routine restart.**

## Verify and test

With the populated dashboard running, open a second terminal in the repository:

```sh
uv run --frozen python scripts/verify_demo.py
```

This checks HTTP health, expected demo counts and all eight pages. It expects the complete demo above and port 8501.

For development tests, start the separate disposable database and fetch the source-backed test fixture:

```sh
docker compose --profile test up -d --wait db-test
uv run --frozen python -m var_analytics.cli migrate --test
uv run --frozen python scripts/audit_sources.py
uv run --frozen python -m pytest -q --tb=short
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Complete step 4 first: supplement tests also need `demo_manifest.json`. Tests use `var_analytics_test` on port 55433 and guard destructive cleanup against the application database. The test database uses temporary storage; rerun its migrations after recreating it. Missing credentials or source fixtures can cause skipped tests—check the summary.

The latest checkpoint passed **49 tests** across two non-overlapping runs (eight ETL tests and 41 remaining tests), plus the live eight-page smoke check with both datasets. The Python commands and Compose configuration were checked on Windows; fresh macOS/Linux installations and the application image have not been exercised. See [verification details](docs/verification.md).

## Troubleshooting

| Symptom | What to check |
|---|---|
| `git`, `uv` or `docker` is not found | Install the prerequisite and open a new terminal so PATH changes take effect. |
| Docker daemon unavailable | Start Docker Desktop/Engine; verify `docker version` shows a server. |
| Database still starting | Check `docker compose ps db` and `docker compose logs --tail 50 db`. Wait for healthy status before migrating. |
| Database port allocated | Stop the conflicting service. To change a port, update both the Compose host port and matching private `.env` URLs. |
| Port 8501 busy | Stop the other app or use `--server.port=8502` and open that port. The smoke checker assumes 8501. |
| Database authentication fails | Use credentials from the database's original setup. Editing environment passwords does not rotate existing passwords; deleting the volume is not a password fix. |
| Missing tables/query error | From the repository root, run `uv run --frozen python -m var_analytics.cli migrate`. |
| Empty dashboard | Complete both imports and clear sidebar date filters; select World Cup 2022. |
| Missing manifest/checksum error | Complete `scripts/fetch_demo.py` before import. Do not edit downloaded provider files. |
| Supplement match mismatch | Import the pinned World Cup demo first. This is not a generic Premier League importer. |
| Existing `.env` preserved | Expected on repeat setup. Continue using it if it belongs to this installation. |

## Add Premier League 2015/16

After completing the database setup, download and import the supported Premier League season:

```sh
uv run --frozen python scripts/fetch_demo.py --dataset premier-league
uv run --frozen python -m var_analytics.cli import-premier-league
```

This retrieves 763 checksummed files into ignored `data/raw/statsbomb-premier-league` and adds **380 matches and 20 clubs** alongside the World Cup. Allow several minutes for the download. Repeating the successful import returns `already_loaded`. Select **Premier League** and **2015/2016** in the sidebar to explore its scores, main referees, players, decisions and cards. With both datasets loaded, Home shows **444 matches** across all leagues.

The season predates VAR, introduced in 2019/20; its VAR page marks this as not applicable. Announced added time and review durations are unavailable. The 15 verified World Cup announcements remain confined to their own matches. Provider clocks are preserved as local times without inventing a timezone.

Verify both loaded datasets while the app is running:

```sh
uv run --frozen python scripts/verify_demo.py --with-premier-league
```

Download this season before running the full development tests to include its mapping, idempotency, coexistence and filter tests. Without those source files, the Premier League tests are skipped. The [source assessment](docs/premier_league_sources.md) records coverage and alternatives for later VAR-era data.

Sportmonks and API-Football document VAR events, but season coverage and field semantics need authenticated sample validation. The importer explicitly supports World Cup 2022 and Premier League 2015/16; it rejects other competition/season combinations.

## Project documents and remaining work

- [Architecture and milestones](docs/implementation_plan.md)
- [ER diagram](docs/er_diagram.md) and [relational schema](docs/relational_schema.md)
- [Environment and skill audit](docs/environment_and_skills.md)
- [Project instructions](AGENTS.md) and [authoritative blueprint](PROJECT_BLUEPRINT.docx)

Protected CSV uploads/manual editing, broader licensed VAR/added-time coverage, full application-container validation and browser visual review remain pending. Stored events and referee responsibility totals do not independently establish decision correctness or referee bias.
