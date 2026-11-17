# Data Management

Open the running dashboard, select **Data Management**, enter the password from your local `.cache/initial-admin-password.txt`, and choose **Sign in**. Analytics pages remain available without this sign-in. Administrator sessions expire after 30 minutes; sign out when finished.

## Choose the records to manage

The page supports matches, official appointments, decisions, team involvement, VAR records, cards, announced added time, match rosters, players, referees, teams, venues, countries, leagues and seasons. It covers every competition in the database; sidebar analytics filters do not restrict this management list. Search by a name or ID to narrow records. Each list shows at most 200 rows ordered by its key.

Database role definitions, lookup vocabularies, credentials, import metadata and materialized views cannot be edited through the record editor. Use **Find related record IDs and valid codes** to locate existing match/team/player IDs and permitted codes. Create missing related records before records that depend on them. Match-roster membership is required before a player's card can be recorded.

## Add a record

1. Choose the record type under **Manage records**, then **Add a record**.
2. Enter source-backed fields. Keep the suggested UUID, or provide your own unused UUID. Related-record IDs must exist. Leave unknown optional values blank.
3. Enter an HTTPS **Source URL** supporting the facts and a **Reason for this change** of at least five characters.
4. Select **Save new record** and check the result. Use **Clear form for another record** when starting the next addition.

The application generates record identifiers, not football observations. It does not look up missing facts from the citation. Only enter VAR outcomes, officials, review durations or announced minutes that the source establishes. A cancelled goal claim should use the reviewed-claim category rather than become a successful goal. VAR was not in use in Premier League 2015/16.

## Preview and import CSV

1. Choose a record type, then **Import CSV**.
2. Download its CSV template. Keep the exact field names; `source_record_id` is assigned by the application and must not be supplied.
3. Fill the template with your verified records and upload it. CSV must be UTF-8 (an optional BOM is supported), no larger than 2,000,000 bytes, with 1–500 data rows. Each row must have the same number of fields as the header.
4. Review the typed preview and any line-level errors. Enter a source URL and change reason for the upload, then confirm that you reviewed the records and their evidence.
5. Select **Import records**. The database checks foreign keys, constraints and triggers at save time. If any row fails, all domain writes in that upload roll back; the attempted upload and rejection status remain in its audit batch.

Imports **add new rows**. They do not overwrite existing provider records. Use **Browse and edit** for corrections. An identical upload with the same citation and reason returns `already_loaded`; it creates no duplicate rows. Failed identical operations require correction or investigation rather than automatic retries.

Independent UUID primary IDs may be blank in CSV: the importer derives deterministic identifiers from the file and row position. Composite keys and relationship IDs must be supplied. Duplicate incoming keys, unknown columns, malformed UUIDs and out-of-range clock fields are rejected. Blank optional fields mean unknown, never zero. The preview checks types and upload structure; live database references and cross-record rules are checked during the save transaction.

Use ISO dates (`YYYY-MM-DD`), local clock times (`HH:MM:SS`) and timezone-aware datetimes when a UTC kickoff is known. A verified timezone name must agree with the local date/time and UTC instant. Seconds must be 0–59; minutes and measured durations must be nonnegative. Match scores must be supplied together, and a completed match requires both scores.

## Edit an existing record

Choose **Browse and edit**, search for the row, and select its exact key under **Record to inspect**. Edit the form, provide the supporting source URL and reason, then select **Save changes**. Record keys are fixed: changing relationships that form a primary key requires adding the correct row and separately deleting the old one if permitted.

If someone else changed the row since it was loaded, the save is rejected. Reload the page/list, review the current record and try again. Every accepted edit attaches a new evidence record; the before-image, submitted fields, original source-record ID, citation, reason and administrator session ID remain in the audit payload. Historical provider evidence is retained.

## Export records

Choose a record type and **Export CSV**. Optionally filter by a name, date text or ID present in that table. For normalized tables such as matches, use the team/match IDs from the reference browser rather than an unrelated display name. The page shows the matching count and a preview of up to 20 records. Select **Download records CSV** to download all matching rows, including rows beyond the 200-record Browse limit.

Exports support up to 20,000 records. If the selection is larger, the app asks you to narrow it and produces no partial file. Empty results produce a header-only CSV. Files use UTF-8 with a BOM for spreadsheet compatibility. UUIDs and operational fields are preserved; unknown values export as blank fields. Private import metadata, raw evidence payloads and credentials are excluded. Text that could become a spreadsheet formula receives an apostrophe prefix in the exported file; stored data is unchanged.

Export is read-only and requires an active administrator session. This is a record-data export, not a full PostgreSQL backup. Existing IDs remain in the file, so importing the same existing rows is deliberately blocked by primary-key checks. Use the editor for corrections. If importing genuinely new records from a larger export, split it into files of at most 500 rows and comply with the 2 MB import limit; do not remove IDs merely to duplicate existing facts.

## Delete an exact record

Under **Browse and edit**, select the row and expand **Delete the selected record**. Inspect the full row, enter a source URL and deletion reason, check the confirmation box, then select **Delete record**. This confirmation is required for each deletion.

The delete targets one primary key. There is no cascade-delete control. PostgreSQL refuses deletion if dependent rows still exist; the page explains that restriction. A stale row is also rejected. Removing a record preserves its existing source evidence and adds an audit record with the before-image and reason. Deletion is permanent in the operational table; review it carefully before confirming.

## Audit history and statistics freshness

Successful and failed operations appear in **Data Quality and Methodology → Import history**. Rejected saves retain their evidence and failure status. Invalid previews are not saved, because the user has not submitted an import. An expired or unauthorized session cannot use the service even if a caller bypasses the UI; PostgreSQL separately enforces `app_admin` privileges. Reader credentials cannot write through this service.

Dashboard analytical queries read saved data immediately. The **referee materialized summary** remains an owner-maintenance operation, using the existing command from a configured owner environment:

```sh
uv run --frozen python -m var_analytics.cli refresh
```

The web app never requires owner credentials to edit records and cannot refresh the materialized view through its administrator connection. Review the summary's freshness on the methodology page after maintenance.

## Implementation and testing boundaries

`admin_service.py` implements the allowlisted table access, Pandas/Pydantic CSV preview, source preservation, session/role checks, optimistic edit checks and transactional mutations. `ui/management.py` provides the native Streamlit controls. The existing PostgreSQL schema/grants are sufficient; no migration or production-data deletion is needed to enable the feature.

For a compact evaluation walkthrough, see [the demonstration checklist](evaluation_demo.md).

Automated mutation tests use only the explicitly guarded `var_analytics_test` database and source-backed test copies. The application demo is checked read-only. Browser appearance and file-selection interaction require a separate visual review; automated CSV parsing and import behavior are tested at the service boundary.
