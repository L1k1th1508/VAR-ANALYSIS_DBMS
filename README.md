# VAR-ANALYSIS_DBMS

Referee & VAR Decision Analytics System, following the November 2026 v3 blueprint.

Current status: approved implementation in progress. The eight-page local dashboard supports a verified World Cup 2022 demonstration: 64 matches, 32 teams, 29 named referees, 1,953 mapped provider events and 228 event-tagged cards. Cited match reports add six selected VAR reviews, three reviewed claims and 15 announced-time records across seven matches. Total decision rows: 1,956. VAR and added-time pages include charts, coverage counts and source links. AVAR appointments and measured review durations remain unavailable.

## Run locally

Use Python 3.11, uv and a running Docker Desktop engine. The existing machine PostgreSQL installation is not used.

```powershell
uv sync --python 3.11
.\.venv\Scripts\python.exe scripts/setup_env.py
docker compose --profile test up -d db db-test
.\.venv\Scripts\python.exe -m var_analytics.cli migrate
.\.venv\Scripts\python.exe -m var_analytics.cli migrate --test
.\.venv\Scripts\python.exe scripts/fetch_demo.py
.\.venv\Scripts\python.exe -m var_analytics.cli import-demo
.\.venv\Scripts\python.exe -m var_analytics.cli import-evidence
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true
```

Open http://127.0.0.1:8501/. After the first import, viewing works offline with the database running. Repeating the import does not duplicate records. `setup_env.py` creates local credentials only when `.env` is absent; keep `.env` and `.cache/initial-admin-password.txt` private. Never remove the database volume as part of a routine restart.

Provider data is downloaded directly from StatsBomb and excluded from this repository. The small cited factual supplement is included in `data/supplements`; original articles and reports are not redistributed. See [source coverage, attribution and limitations](docs/source_coverage.md). The imported data stays in the PostgreSQL volume.

## Verify

```powershell
.\.venv\Scripts\python.exe scripts/audit_sources.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
```

Tests use the separate `var_analytics_test` database on port 55433. Application data uses port 55432. The source audit downloads the three real matches used by ingestion/integrity tests. Test-only malformed copies never enter the demo database.

Remaining project work includes additional licensed VAR/added-time coverage, protected CSV management workflows, full container deployment validation and browser visual review. Data Management currently provides authentication; it does not yet provide uploads or manual edits.

## Planning documents

- [Architecture and milestone plan](docs/implementation_plan.md)
- [ER diagram](docs/er_diagram.md)
- [Proposed relational schema](docs/relational_schema.md)
- [Environment and skill audit](docs/environment_and_skills.md)
- [Project instructions](AGENTS.md)
- [Authoritative blueprint](PROJECT_BLUEPRINT.docx)

Required stack: PostgreSQL 16, Python 3.11, SQLAlchemy 2.0, Pandas, Pydantic, Streamlit, Plotly, Docker Compose and Pytest.

All eight dashboard pages and the three PostgreSQL roles are included in the plan. Football data must be source-backed and traceable; unavailable VAR details will not be fabricated.
