# Level 3 evaluation preparation

The supplied PES Level 3 rubric totals 50 marks. The team approved extending the original PostgreSQL/Streamlit blueprint on 17 November 2026 to include Next.js and MongoDB. The original football schema and Streamlit workflows remain the base of the application. The new portal demonstrates web integration and a separate document-oriented research notebook.

## Rubric evidence map

| Criterion | Marks | Concrete evidence |
|---|---:|---|
| ER diagram | 2 | docs/er_diagram.md is the implemented relational model; chen-complete.png is a presentation diagram |
| Relational schema and constraints | 3 | docs/relational_schema.md and sql/migrations/001_schema.sql |
| SQL DDL | 4 | Ordered checksummed migrations; constraints and PL/pgSQL trigger functions |
| NoSQL/vector database creation | 4 | MongoDB research-db service in compose.evaluation.yaml; validated notes collection created during database initialization |
| Technology justification | 1 | PostgreSQL for referential integrity and analytical joins; MongoDB for independent research documents; Next.js for server routes and browser interface |
| DML | 4 | Existing authenticated AdminService and Data Management forms/CSV import/export |
| Nested/correlated/join queries | 4 | sql/evaluation_queries.sql examples 1–3 |
| Function, trigger, CTE | 6 | assert_participant and other SQL trigger functions; example 4; materialized view CTEs |
| NoSQL RUD | 7 | Portal notebook lists, edits and deletes MongoDB documents, with source URL and optimistic version checks |
| Next.js | 3 | evaluation-web app router, analytics/session/notes routes, browser page |
| Backend integration | 2 | Server-side Python bridge reuses AnalyticsService; MongoDB driver stays on the server |
| Authentication and database roles | 4 | Argon2 application authentication; db_owner, app_reader, app_admin grants; portal HttpOnly session |
| Documentation and Git | 2 | This guide, original docs, commits and implementation branch |
| Originality and individual viva | 4 | Team must honestly explain and demonstrate its own work using the questions below |

The map indicates where to demonstrate a criterion. Marks depend on correct execution and the evaluator's interpretation. MongoDB is the NoSQL option in the rubric; this implementation does not claim vector search.

## Start the evaluation portal

Complete the README database setup and source imports first. From the repository root run:

```sh
docker compose -f compose.yaml -f compose.evaluation.yaml up -d --build --wait evaluation-web
```

Open http://127.0.0.1:3000. PostgreSQL remains on its existing volume. MongoDB has a separate named volume and no published host port. The portal uses the same local administrator password as Streamlit, stored in .cache/initial-admin-password.txt. Streamlit is separately available on port 8501 when started using the README command. The portal's dashboard link is intended for local demonstration.

The Python bridge executes inside the web server container, never in the browser. It has reader credentials for PostgreSQL. Notebook mutations require an authenticated session and matching request origin. Sessions last 30 minutes. Changing the configured password hash invalidates old signed cookies. Notebook edit/delete operations include the observed integer revision and reject stale modifications.

PostgreSQL remains authoritative for imported football facts. MongoDB stores explicitly identified analyst notes with a title, body, evidence URL, creation and update timestamps. It does not duplicate an entire relational season or invent missing football observations. Notebook listing is capped at the latest 100 notes and the UI states this limit. MongoDB is an independent store, so there is no cross-database atomic transaction. A research note is not a verified import batch.

## A twelve-minute demonstration

1. Explain the problem and show the current ER diagram. Identify the home/away foreign keys, composite official key and match-player bridge.
2. Open the portal and show live PostgreSQL totals and fixtures. Open Streamlit for filtering and all eight analytical pages.
3. Trace a selected decision back through source_record, import_batch and data_source. State coverage limits before interpreting a rate.
4. Open Data Management. Demonstrate CSV preview and a source-backed addition in the isolated test/demo environment. Explain all-or-nothing rollback and show import history.
5. Run the read-only SQL examples in sql/evaluation_queries.sql. Explain joins, correlated queries, CTE and dense_rank.
6. Show a negative integrity test and reader-write rejection from the test suite. Use the guarded test DB for invalid writes.
7. Sign into the portal. Create an analyst note with real evidence URL, reload it, edit it and delete it after confirmation. Show the note collection through mongosh if requested. Explain what a document ID and incrementing revision do.
8. Finish with data limitations, actual test results and the contribution history. Identify one extension each teammate can explain independently.

## Viva questions and answers

**Why two databases?** Relational football facts need joins and referential integrity. A research annotation is an independent document with a source URL and free text. The notebook demonstrates a distinct NoSQL use case. Cross-store references are not foreign keys and do not participate in a distributed transaction.

**Why not store current team on player?** A player can transfer. match_player captures the team represented in the specific historical match, and card_issued references that membership.

**Explain 1NF, 2NF and 3NF here.** Atomic operational values and separate rows for repeated relationships support 1NF. Non-key fields in bridge tables describe the full relationship key, supporting 2NF. League belongs to season rather than being repeated as an independently mutable match field, and card team derives from match participation, avoiding transitive dependencies. Normalization needs an explanation of dependencies, not just a count of tables.

**Why composite appointment keys?** A match, role and slot identify one appointment. The referee is its value. Composite foreign keys prevent attributing a decision to an appointment from another match.

**Why a trigger instead of CHECK?** A row CHECK should inspect its own values. Checking whether a decision team is one of the fixture participants crosses table boundaries; the trigger locks referenced records and verifies that relationship. Foreign keys still enforce existence.

**What happens if the second row of an upload fails?** Domain writes run in one transaction and roll back. Audit handling retains the submitted evidence and failed status. Check service and tests for the precise savepoint/transaction boundaries.

**What is idempotency?** Input fingerprint plus transform version identifies repeat imports. A successful identical batch returns already_loaded; a new mapping version is a distinct operation. Failed batches need inspection rather than blind retry.

**How do you avoid inflated aggregates?** Aggregate decisions, cards and reviews independently before joining at match grain. Joining raw one-to-many child sets would multiply rows and overcount.

**What is a window function?** It calculates across a partition while retaining individual result rows. dense_rank ranks referee responsibilities within each season and gives tied values the same rank.

**What is a materialized view?** Stored query output. It accelerates repeated reads but becomes stale until owner refresh. Ordinary views are query definitions evaluated against current base data. Small datasets may legitimately use sequential scans even with indexes.

**Explain the overturn rate.** Overturned recorded review outcomes divided by recorded known eligible outcomes. Unknowns are excluded and shown separately. NULLIF avoids division by zero. The small selected sample does not establish a tournament-wide overturn rate or referee bias.

**Authentication versus authorization?** Argon2 verifies the submitted password. Application sessions gate controls. PostgreSQL independently denies writes from app_reader and reserves maintenance for db_owner. Hiding a button alone cannot enforce permissions.

**How does MongoDB prevent a lost edit?** updateOne filters by both _id and the previously observed revision. A concurrent change makes matchedCount zero and yields HTTP 409. Delete uses the same guard. MongoDB mutations are single-document atomic operations.

**Why is raw JSONB compatible with relational normalization?** Raw provider payloads preserve evidence. Operational facts are modeled relationally for constraints and joins. JSONB is PostgreSQL storage and does not alone demonstrate a separate NoSQL database.

**Why do kickoff fields have nullable timezone?** A local clock is not a verified UTC instant. The importer preserves source date/time and leaves UTC unknown unless the timezone is evidenced.

**Does this match the earlier ER image?** The conceptual subject areas align, but the implemented schema has composite keys, player participation and provenance, and different card/added-time relationships. Use docs/er_diagram.md and the live constraints when explaining exact implementation. Update presentation diagrams to those definitions rather than claiming the old image is exact.

**What would you improve next?** Paginated research listing, operational monitoring and full browser accessibility review. Explain tradeoffs honestly. Database permissions, sample sizes and source coverage still apply during a live demonstration.

## Individual preparation

Each teammate should explain one end-to-end record from source bytes through validation, transaction, foreign keys, service query and UI. Assign ownership honestly in the presentation; Git commits are evidence of changes, not proof of understanding. Practice adding a query filter, explaining a constraint rejection, tracing a failed upload and diagnosing a stale notebook edit without reading a memorized answer.

## Technical references

- [Next.js Route Handlers](https://nextjs.org/docs/app/getting-started/route-handlers)
- [MongoDB schema validation](https://www.mongodb.com/docs/manual/core/schema-validation/)
- [PostgreSQL 16 constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)
- [PostgreSQL 16 transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html)

## Repeatable portal verification

With the portal running on local port 3000, run `uv run --frozen python scripts/verify_portal.py`. It uses this checkout's initial-password file, checks authentication, authorization, validation, MongoDB create/read/update/delete, stale-write conflicts, origin protection and sign-out. It creates and removes one explicitly temporary software-test annotation. It does not modify imported football facts. If you have rotated the password, align the local initial-password file deliberately before running this local check.
