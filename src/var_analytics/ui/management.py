"""Native Streamlit record maintenance with previews and explicit save controls."""

import hashlib
from pathlib import Path
from uuid import UUID, uuid4

import pandas as pd
import streamlit as st

from var_analytics.admin_service import ENTITIES, AdminService, serial

CHOICES = {
    "status": ["scheduled", "live", "completed", "postponed", "cancelled", "abandoned"],
    "card_type": ["yellow", "second_yellow", "red"],
    "review_kind": ["check", "review"],
    "involvement_code": ["recorded_team", "opponent", "beneficiary", "penalized"],
    "competition_kind": ["domestic", "international"],
}


def display_ids(frame):
    """Render PostgreSQL UUID values as plain text in Streamlit tables."""
    visible = frame.copy()
    for column in visible.columns:
        if visible[column].map(lambda value: isinstance(value, UUID)).any():
            visible[column] = visible[column].map(
                lambda value: str(value) if isinstance(value, UUID) else value
            )
    return visible


def announce(result):
    if result["status"] == "already_loaded":
        st.success(f"Already imported. No duplicate records added. Batch {result['batch_id']}.")
    else:
        st.success(f"Saved {result['records']} record(s). Evidence retained in batch {result['batch_id']}.")
    st.caption(
        "Dashboard queries use the saved data immediately. The referee materialized summary "
        "requires the owner's documented refresh command."
    )


def evidence_inputs(prefix):
    citation = st.text_input(
        "Source URL", key=f"{prefix}_citation", help="An HTTPS report or dataset supporting these facts."
    )
    reason = st.text_area(
        "Reason for this change",
        key=f"{prefix}_reason",
        help="Explain the source-backed addition or correction. At least five characters.",
    )
    return citation, reason


def record_inputs(service, entity, prefix, original=None):
    values = {}
    primary = {c.name for c in service.table(entity).primary_key}
    for column in service.fields(entity):
        name = column.name
        generated = column.primary_key and column.type.python_type is UUID and not column.foreign_keys
        locked = original is not None and name in primary
        label = name.replace("_", " ").capitalize().replace(" id", " ID")
        value = original.get(name) if original else None
        if generated and original is None:
            value = st.session_state.setdefault(f"{prefix}_new_id", str(uuid4()))
        default = "" if value is None else str(value)
        help_text = "Leave blank if unknown." if column.nullable else "Required."
        if generated and original is None:
            help_text = "Suggested new record UUID. Keep it or provide your own unused UUID."
        options = CHOICES.get(name)
        if name == "official_role_code":
            options = service.reference_rows("official_role").role_code.tolist()
        if name == "outcome_code":
            outcomes = service.reference_rows("decision_outcome")
            scope = "var" if entity == "var_involvement" else "decision"
            options = outcomes[outcomes.outcome_scope == scope].outcome_code.tolist()
        if not options:
            foreign = next(iter(column.foreign_keys), None)
            if foreign and foreign.column.type.python_type is str:
                options = service.reference_rows(foreign.column.table.name)[foreign.column.name].tolist()
        if options and not locked:
            options = ["", *options]
            values[name] = st.selectbox(
                label,
                options,
                index=options.index(default) if default in options else 0,
                key=f"{prefix}_{name}",
                help=help_text,
            )
        else:
            values[name] = st.text_input(
                label, value=default, disabled=locked, key=f"{prefix}_{name}", help=help_text
            )
    return values


def references(service, entity):
    with st.expander("Find related record IDs and valid codes"):
        targets = service.references(entity)
        if not targets:
            st.caption("This record has no editable links to other tables.")
            return
        selected = st.selectbox("Related records", targets, key=f"refs_{entity}")
        if selected in ENTITIES:
            search = st.text_input("Find a name or ID", key=f"ref_search_{entity}_{selected}")
            frame = service.browse(selected, search).drop(columns="source_record_id", errors="ignore")
        else:
            frame = service.reference_rows(selected)
        st.dataframe(display_ids(frame), hide_index=True, width="stretch")
        st.caption(
            "Showing up to 200 records. Copy the required ID into the form or CSV. "
            "Create missing related records first."
        )


def render(session):
    service = AdminService(session)
    entity = st.selectbox("Manage records", list(ENTITIES), format_func=ENTITIES.get, key="manage_entity")
    action = st.radio(
        "Action",
        ["Browse and edit", "Add a record", "Import CSV", "Export CSV"],
        horizontal=True,
        key="manage_action",
    )
    st.caption(
        "Management covers all competitions. Enter verified facts and leave unknown values blank. "
        "Each save retains its source citation, reason and original evidence."
    )
    references(service, entity)
    try:
        if action == "Export CSV":
            st.subheader("Export records to CSV")
            search = st.text_input("Filter export by name or ID", key=f"export_search_{entity}")
            result = service.export_csv(entity, search)
            st.write(f"{len(result.rows):,} matching records")
            st.dataframe(pd.DataFrame(serial(result.rows)).head(20), hide_index=True, width="stretch")
            st.caption(
                "Preview shows up to 20 rows; the download includes every matching row, up to 20,000. "
                "Blank fields stay unknown. Private import metadata and credentials are excluded."
            )
            st.download_button(
                "Download records CSV",
                result.content,
                file_name=f"{entity}_records.csv",
                mime="text/csv",
                key=f"export_download_{entity}",
            )
            st.caption(
                "Existing record IDs are preserved. Re-importing existing IDs is blocked; use Browse and edit "
                "for corrections. Larger exports must be split into 500-row files before any new-record import."
            )
        elif action == "Import CSV":
            st.subheader("Preview a CSV before importing")
            st.download_button(
                "Download CSV template",
                service.template(entity),
                file_name=f"{entity}_template.csv",
                mime="text/csv",
            )
            if entity == "added_time":
                example = Path(__file__).resolve().parents[3] / "data/demo/verified_added_time_import.csv"
                if example.exists():
                    st.download_button(
                        "Download verified evaluation CSV",
                        example.read_bytes(),
                        file_name="verified_added_time_import.csv",
                        mime="text/csv",
                    )
                    st.markdown(
                        "Example: Liverpool–Arsenal, 13 January 2016, second half: three announced minutes. "
                        "[Source: live coverage, 90+1 entry](https://www.theguardian.com/football/live/2016/jan/13/liverpool-v-arsenal-premier-league-live). "
                        "Requires the loaded 2015/16 Premier League season; importing an existing period is blocked."
                    )
            st.caption(
                "UTF-8 CSV, at most 2 MB / 500 rows. Blank means unknown. UUID primary IDs can be blank "
                "for new records; relationship IDs must refer to existing records. Imports add records; "
                "use Browse and edit for corrections."
            )
            upload = st.file_uploader("CSV file", type="csv", max_upload_size=2, key=f"upload_{entity}")
            if upload is not None:
                content = upload.getvalue()
                preview = service.preview_csv(entity, content)
                if not preview.errors.empty:
                    st.error("Fix these errors before importing.")
                    st.dataframe(preview.errors, hide_index=True, width="stretch")
                st.dataframe(pd.DataFrame(serial(preview.rows)), hide_index=True, width="stretch")
                st.caption(
                    "Preview checks fields and duplicate upload keys. Saving also checks current database "
                    "references and integrity rules; any rejection rolls back the entire upload."
                )
                citation, reason = evidence_inputs(f"csv_{entity}")
                reviewed = st.checkbox(
                    "I reviewed these records and their source evidence",
                    key=f"csv_reviewed_{entity}_{hashlib.sha256(content).hexdigest()}",
                )
                if st.button(
                    "Import records", disabled=not preview.valid or not reviewed, key=f"import_{entity}"
                ):
                    announce(service.import_csv(entity, content, citation, reason))
        elif action == "Add a record":
            st.subheader("Add a source-backed record")
            if st.button("Clear form for another record", key=f"clear_add_{entity}"):
                for key in list(st.session_state):
                    if key.startswith(f"add_{entity}_"):
                        del st.session_state[key]
                st.rerun()
            with st.form(f"add_{entity}"):
                values = record_inputs(service, entity, f"add_{entity}")
                citation, reason = evidence_inputs(f"add_{entity}")
                save = st.form_submit_button("Save new record")
            if save:
                announce(service.create(entity, values, citation, reason))
        else:
            search = st.text_input("Search records by name or ID", key=f"search_{entity}")
            frame = service.browse(entity, search)
            st.dataframe(display_ids(frame), hide_index=True, width="stretch")
            st.caption("Up to 200 records, ordered by record key. Search to narrow the list.")
            if frame.empty:
                st.info("No records found. Change the search or add a verified record.")
                return
            primary = [c.name for c in service.table(entity).primary_key]
            labels = [
                " / ".join(str(row[k]) for k in primary) + (f" — {row['name']}" if "name" in row else "")
                for row in frame.to_dict("records")
            ]
            selected = st.selectbox(
                "Record to inspect",
                range(len(frame)),
                format_func=lambda i: labels[i],
                key=f"edit_select_{entity}",
            )
            keys = {k: frame.to_dict("records")[selected][k] for k in primary}
            original = service.get(entity, keys)
            # The source revision is part of widget keys, so a reload after saving shows current values.
            prefix = f"edit_{entity}_{labels[selected]}_{original['source_record_id']}"
            st.subheader("Edit the selected record")
            with st.form(prefix):
                values = record_inputs(service, entity, prefix, original)
                citation, reason = evidence_inputs(prefix)
                save = st.form_submit_button("Save changes")
            if save:
                announce(service.update(entity, original, values, citation, reason))
            with st.expander("Delete the selected record"):
                st.write(
                    "Deletion removes this record only. Linked records may prevent deletion. "
                    "Its source evidence and the before-image remain in the audit history."
                )
                st.json(serial(original))
                delete_citation, delete_reason = evidence_inputs(f"delete_{prefix}")
                confirmed = st.checkbox(
                    "I confirm deletion of this exact record", key=f"delete_confirm_{prefix}"
                )
                if st.button("Delete record", disabled=not confirmed, key=f"delete_{prefix}"):
                    announce(
                        service.delete(entity, original, delete_citation, delete_reason, confirmed=confirmed)
                    )
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))
