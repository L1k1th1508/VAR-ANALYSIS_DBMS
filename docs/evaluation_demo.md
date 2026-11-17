# Data Management evaluation walkthrough

This checklist covers CSV import/export, add/edit/delete, validation and database roles. Use real cited records. Perform destructive examples only in a disposable demonstration/test database; the automated tests already use guarded, source-backed test copies.

## Show the current page

Open the running dashboard, select **Data Management** and sign in. You should see **Manage records** and four actions: **Browse and edit**, **Add a record**, **Import CSV**, **Export CSV**. If the page instead says manual editing is unavailable, it is an older server process. Stop that Streamlit process, launch from the current project folder and refresh the browser. The two project copies on this machine have different local passwords; use the `.cache/initial-admin-password.txt` belonging to the running copy.

## Explain and demonstrate each criterion

| Criterion | What to show | Evidence / expected result |
|---|---|---|
| Authentication | Open Data Management before and after sign-in | Maintenance controls are available only after administrator sign-in; the service also checks session capability and expiry |
| Browse/reference lookup | Select Matches, Decisions or Cards; search by an ID and expand the reference browser | Normalized rows and their existing foreign-key IDs; no owner-only table editor |
| Export | Choose a record type → Export CSV → inspect count/preview → Download records CSV | UTF-8 file with headers, stable IDs, blank unknown values and every matching row up to the explicit cap |
| CSV preview | Import CSV → Download CSV template → upload verified new records | Typed preview and line-level validation errors; review confirmation required before Import records |
| Valid import | Submit a valid new-record CSV with citation and reason in the disposable demo | Rows appear; import history shows accepted count and a successful batch; duplicate submission returns already_loaded |
| Invalid import | Try an invalid UUID, seconds value 60, missing related ID or existing primary key in the disposable demo | Preview errors or a database rejection; a failed transaction leaves no partial domain writes |
| Add/edit | Enter a verified record, then correct a field with a source URL and reason | Saved row and new source evidence; primary keys remain fixed; a stale edit is rejected |
| Delete | Inspect a selected record, open Delete, supply citation/reason and confirm | Only that exact key is deleted when permitted; linked records block deletion; before-image remains in the audit evidence |
| Roles | Explain db_owner, app_reader and app_admin | Reader writes are denied by PostgreSQL; administrator CRUD is limited; materialized-view refresh remains owner maintenance |
| Provenance | Open Data Quality and Methodology → Import history | Source, counts, timestamps and success/failure status; original JSONB evidence remains stored in the database |

The CSV preview does not promise that every database relationship is valid. Those rules are checked at save time against the current database state. A batch containing a valid first row and an invalid later row rolls back entirely.

## Repeatable verification without changing the demo

### A real CSV for the positive import demonstration

`data/demo/verified_added_time_import.csv` contains one manually verified factual annotation for Liverpool–Arsenal (3–3, 13 January 2016): period 2, **three announced minutes**, seconds unknown. The [live report's 90+1 entry](https://www.theguardian.com/football/live/2016/jan/13/liverpool-v-arsenal-premier-league-live) explicitly gives that announcement. The match was reconciled to StatsBomb's pinned 2015/16 match ID 3754305. This is a cited annotation, not a provider-feed redistribution or an inferred final-whistle duration.

1. Load Premier League 2015/16 using the README commands before demonstrating this file.
2. Choose **Announced added time → Import CSV → Download verified evaluation CSV**, then upload that downloaded file.
3. Use the linked live-report URL as the source citation. Enter a reason such as “Add the verified second-half announcement from the cited live report.”
4. Inspect the one-row preview, check the review confirmation and select **Import records**.
5. Search that match's UUID under **Browse and edit**, then use **Export CSV** with the same match ID to download the new record. Open Import history to show its accepted batch.

This file is supplied for explicit import, not preloaded by setup. If the period already exists, the database blocks a conflicting new insert. Repeating an identical successful import with unchanged citation/reason returns `already_loaded`. Keep the announcement value accurate when demonstrating edits; use a source-supported correction or updated citation rather than inventing another time. Delete only after selecting the exact row and confirming if your demonstration requires it; evidence is preserved.

The baseline smoke checker below expects the original three historical announcements. Run it before this positive import. Keeping the extra verified record intentionally changes the baseline's announcement count; that is not an import failure. For repeatable write/delete checks without changing the application demo, use the disposable automated tests.

### Automated checks

Start the disposable test database and fetch the documented source fixtures first, following the README. Then run:

```sh
uv run --frozen python -m pytest tests/test_admin.py tests/test_ui.py -q --tb=short
```

These tests exercise authenticated CRUD, before/after evidence, CSV parsing/import, repeated imports, stale edits, restricted deletion, expired sessions, reader-role denial and the page controls. Export tests check that downloads exceed the 200-row Browse limit without truncation, preserve columns/unknowns, respect filtering and authorization, and reject an oversized selection rather than silently shorten it. Test-only copies and malformed data stay in `var_analytics_test`.

With the application running, verify the read-only dashboard and loaded real datasets:

```sh
uv run --frozen python scripts/verify_demo.py --with-premier-added-time
```

This checks all eight pages and expected World Cup/Premier League counts. For a different local port, append `--port 8502` or the port you selected. Do not rerun credential setup or delete the PostgreSQL volume to refresh the UI.

After administrator writes that affect referee totals, an owner can run the documented `var_analytics.cli refresh` command. The live analytical queries read the new data immediately; the materialized summary exposes its own freshness.
