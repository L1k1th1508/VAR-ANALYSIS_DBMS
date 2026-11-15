# VAR-ANALYSIS_DBMS

Referee & VAR Decision Analytics System, following the November 2026 v3 blueprint.

Current status: planning complete for review; awaiting user approval before implementation.

## Planning documents

- [Architecture and milestone plan](docs/implementation_plan.md)
- [ER diagram](docs/er_diagram.md)
- [Proposed relational schema](docs/relational_schema.md)
- [Environment and skill audit](docs/environment_and_skills.md)
- [Project instructions](AGENTS.md)
- [Authoritative blueprint](PROJECT_BLUEPRINT.docx)

Required stack: PostgreSQL 16, Python 3.11, SQLAlchemy 2.0, Pandas, Pydantic, Streamlit, Plotly, Docker Compose and Pytest.

All eight dashboard pages and the three PostgreSQL roles are included in the plan. Football data must be source-backed and traceable; unavailable VAR details will not be fabricated.
