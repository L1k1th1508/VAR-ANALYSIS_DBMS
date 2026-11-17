# Referee & VAR Decision Analytics System — Codex Instructions

Read `PROJECT_BLUEPRINT.docx` before architecture or implementation work. The blueprint is authoritative; if a requested change conflicts, flag it and ask first.

## Approved stack
PostgreSQL 16, Python 3.11, SQLAlchemy 2.0, Pandas, Pydantic, Streamlit, Plotly, Docker Compose, Pytest. No React, Neo4j or MongoDB in v1 unless explicitly approved.

## Skill routing
- Schema, ERD, SQL, integrity, analytics SQL: postgres-design
- Database roles, permissions, admin security: postgres-rbac
- API/CSV/JSON ingestion, validation, SQLAlchemy: python-etl
- Eight Streamlit pages, UI/UX, Plotly: streamlit-plotly and frontend-design (adapt to Streamlit)
- Containers and deployment: docker-deployment
- Tests and validation: pytest-quality

## Non-negotiable requirements
Preserve source provenance and distinguish real versus synthetic data. Do not fabricate unavailable VAR details, AVAR names, or review durations. Use 3NF schema, constraints, triggers, and the referee statistics materialized view. Implement db_owner, app_reader and app_admin with database-level least privilege, plus separate application authentication. All eight pages are required. Provide a preloaded offline demo.

## Workflow
1. Inspect existing files and summarize current state.
2. Make a scoped plan and identify affected modules.
3. Implement in small, verifiable increments.
4. Run relevant tests and report exact outcomes.
5. Ask before destructive database changes, installing untrusted dependencies, or changing approved stack.
6. Never commit secrets; use .env.example and ignored .env.

## Approved Level 3 extension

On 17 November 2026 the user approved extending the stack to satisfy the supplied Level 3 rubric. Next.js and MongoDB are permitted for the evaluation portal and cited research notebook described in docs/level3_readiness.md. PostgreSQL remains the authoritative store for football facts. Existing source-provenance, least-privilege and integrity requirements apply. Research notes must be identified as analyst annotations and must not invent missing football observations.
