# Referee & VAR Decision Analytics

An eight-page dashboard for football matches, referee assignments, decisions, VAR reviews and announced added time. Built with PostgreSQL 16, Python 3.11, SQLAlchemy 2.0, Pandas, Pydantic, Streamlit, Plotly, Docker Compose and Pytest.

The setup below downloads real World Cup 2022 data into your own local database. **No API key is needed.** The commands work in Windows PowerShell, macOS Terminal and Linux shells; `uv run` selects the project environment without OS-specific activation commands.

## What is included

| Page | Contents |
|---|---|
| Home Dashboard | Match, team, referee and decision totals |
| Match Explorer | Scores, appointments, event chronology and source evidence |
| Referee Analytics | Recorded match responsibilities, cards and penalty shots |
| VAR Analytics | 27 cited World Cup interventions, outcomes, categories and source reports |
| Team Analytics | Recorded team involvement, cards and penalty shots |
| Added Time Analytics | Announced minutes by period and match, with citations |
| Data Management | Administrator sign-in, CSV previews/imports/exports, record forms, edits and confirmed deletions |
| Data Quality and Methodology | Import history, validation, coverage and limitations |

The full World Cup demo has **64 matches, 32 teams, 29 named referees, 1,966 decision rows and 228 event-tagged cards**. Decision rows comprise 1,953 provider events and 13 reviewed claims. Two cited supplements provide **27 VAR interventions (25 overturns, two retained decisions)** and **15 announced-time records across seven matches**. The intervention count includes a separate penalty-retake decision; routine checks are not catalogued. Announced-time coverage is partial. Review durations and VAR/AVAR appointments remain unavailable; no synthetic football data is used. See the [sources and counting rules](docs/source_coverage.md#world-cup-2022-var-completion).

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
uv run --frozen python -m var_analytics.cli import-world-cup-var
```

The download retrieves 131 files from a pinned StatsBomb revision into ignored `data/raw/statsbomb`. Allow several minutes depending on your connection. Import validates hashes and records and preserves provenance. Load the main demo **before** the supplement: the supplement reconciles against existing match/event IDs.

Successful imports print a result with `status` set to `success`. Repeating an identical successful import returns `already_loaded` without duplicating records. Failed/pending batches require inspection rather than silent retries. Each import refreshes the referee materialized summary through owner maintenance.

Provider files are downloaded directly, not redistributed here. Review [StatsBomb attribution guidance](https://github.com/hudl/open-data) and the [pinned license](https://github.com/hudl/open-data/blob/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/LICENSE.pdf). The included factual supplement contains citations, not source articles. See [field mappings and coverage](docs/source_coverage.md).

## 5. Launch the dashboard

```sh
uv run --frozen streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true
```

Open **[http://127.0.0.1:8501/](http://127.0.0.1:8501/)** on the same computer. Keep the terminal running. FIFA World Cup season selector shows **2022** and Home shows **64 matches and 27 recorded VAR reviews**.

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
uv run --frozen python scripts/verify_demo.py --with-world-cup-var
```

This checks HTTP health, expected demo counts and all eight pages. It expects the complete demo above. If Streamlit is running on another port, pass it with `--port`, for example `--port 8502`.

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

The latest full regression run passed **77 tests**. The subsequent World Cup VAR completion and league-season changes passed **12 targeted tests**, plus all eight populated page checks. Earlier verification includes authenticated record management, CSV import/export, validation and read-only checks of all 15 administrator form/export types. A cited evaluation CSV is supplied for an explicit import demonstration. The Python commands and Compose configuration were checked on Windows; fresh macOS/Linux installations and the application image have not been exercised. See [verification details](docs/verification.md).

## Troubleshooting

| Symptom | What to check |
|---|---|
| `git`, `uv` or `docker` is not found | Install the prerequisite and open a new terminal so PATH changes take effect. |
| Docker daemon unavailable | Start Docker Desktop/Engine; verify `docker version` shows a server. |
| Database still starting | Check `docker compose ps db` and `docker compose logs --tail 50 db`. Wait for healthy status before migrating. |
| Database port allocated | Stop the conflicting service. To change a port, update both the Compose host port and matching private `.env` URLs. |
| Port 8501 busy | Stop the other app or launch Streamlit with `--server.port=8502` and run the smoke checker with `--port 8502`. |
| Database authentication fails | Use credentials from the database's original setup. Editing environment passwords does not rotate existing passwords; deleting the volume is not a password fix. |
| Missing tables/query error | From the repository root, run `uv run --frozen python -m var_analytics.cli migrate`. |
| Empty dashboard | Complete all three demo imports and clear sidebar date filters; select World Cup 2022. |
| Missing manifest/checksum error | Complete `scripts/fetch_demo.py` before import. Do not edit downloaded provider files. |
| Supplement match mismatch | Import the pinned World Cup demo first. |
| Existing `.env` preserved | Expected on repeat setup. Continue using it if it belongs to this installation. |

## Project documents and remaining work

Data Management is available after administrator sign-in. It supports CSV templates and previews (UTF-8, up to 2 MB / 500 import rows), filtered CSV exports (up to 20,000 rows), source-backed additions and corrections, reference-ID searches and confirmed deletion of an exact record. Failed imports roll back, and every accepted change retains provenance. See the [Data Management guide](docs/data_management.md) and [evaluation walkthrough](docs/evaluation_demo.md).

- [Architecture and milestones](docs/implementation_plan.md)
- [ER diagram](docs/er_diagram.md) and [relational schema](docs/relational_schema.md)
- [Environment and skill audit](docs/environment_and_skills.md)
- [Project instructions](AGENTS.md) and [authoritative blueprint](PROJECT_BLUEPRINT.docx)

Broader licensed VAR/added-time coverage, full application-container validation and browser visual review remain pending. Stored events and referee responsibility totals do not independently establish decision correctness or referee bias.
