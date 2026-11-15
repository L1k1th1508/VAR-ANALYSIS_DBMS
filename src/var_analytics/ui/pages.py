from functools import wraps

import plotly.express as px
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from var_analytics.analytics_service import AnalyticsService, Scope, rate
from var_analytics.auth import authenticate, require_admin

COLORS = ["#236FA1", "#236B5B", "#9A5A00", "#B23A48", "#79589F", "#536774"]


def page(title):
    def decorate(fn):
        @wraps(fn)
        def render():
            st.title(title)
            try:
                fn(AnalyticsService(), st.session_state.get("scope", Scope()))
            except SQLAlchemyError:
                st.error(
                    "The database query could not run. Check database health and apply the documented migrations."
                )

        return render

    return decorate


def show_table(frame):
    st.dataframe(frame, hide_index=True, width="stretch")


def chart(frame, x, y, title, **kwargs):
    fig = px.bar(frame, x=x, y=y, title=title, color_discrete_sequence=COLORS, **kwargs)
    fig.update_layout(
        font_family="Source Sans 3, Arial, sans-serif",
        font_color="#18354A",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=12, r=12, t=55, b=20),
    )
    fig.update_xaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch")


def empty(
    frame, reason="No records match these filters. Choose another scope or load an approved source dataset."
):
    if frame.empty:
        st.info(reason)
        return True
    return False


@page("Home Dashboard")
def home(service, scope):
    totals = service.totals(scope)
    for col, key, label in zip(
        st.columns(5),
        ["matches", "teams", "referees", "decisions", "reviews"],
        ["Matches", "Teams", "Referees", "Recorded decisions", "Recorded VAR reviews"],
    ):
        col.metric(label, int(totals[key]))
    st.caption("Counts describe stored records. No recorded VAR reviews does not mean no reviews occurred.")
    catalog = service.catalog(scope)
    if not empty(catalog):
        counts = catalog.groupby(["league", "season"], dropna=False).size().reset_index(name="matches")
        chart(counts, "season", "matches", "Matches in the selected scope", color="league")
        show_table(
            catalog[["match_date", "home_team", "away_team", "home_score", "away_score", "main_referee"]]
        )
    st.caption(
        "Local demo: FIFA World Cup 2022, supplied by StatsBomb Open Data. "
        "Recorded events include fouls (including advantage), goals and penalty shots; "
        "they are not independent judgments of referee correctness."
    )
    st.info(
        "VAR outcomes, AVAR appointments, review durations and announced added time are unavailable "
        "in this source. Match, referee and team analytics use the recorded evidence."
    )


@page("Match Explorer")
def matches(service, scope):
    catalog = service.catalog(scope)
    if empty(catalog):
        return
    labels = {
        row.match_id: f"{row.match_date}: {row.home_team} vs {row.away_team}" for row in catalog.itertuples()
    }
    selected = st.selectbox("Match", list(labels), format_func=labels.get)
    row = catalog[catalog.match_id == selected].iloc[0]
    st.subheader(f"{row.home_team}  {row.home_score} : {row.away_score}  {row.away_team}")
    st.caption(
        f"Source date: {row.match_date}. Kickoff clock: {row.kickoff_local}. "
        f"Timezone: {row.timezone_name or 'unavailable'}."
    )
    st.write("Recorded appointments")
    show_table(service.officials(selected))
    timeline = service.timeline(selected)
    if empty(timeline, "No supported decision, card or review records are stored for this match."):
        return
    known = timeline[timeline.minute.notna()]
    chronology, evidence = st.columns([2, 1])
    with chronology:
        if not known.empty:
            fig = px.scatter(
                known,
                x="minute",
                y="event",
                color="event",
                symbol="event",
                facet_row="period_code",
                hover_data=["description", "second"],
                color_discrete_sequence=COLORS,
                title="Decision chronology by recorded period",
            )
            fig.update_layout(showlegend=False, height=max(350, known.period_code.nunique() * 170))
            st.plotly_chart(fig, width="stretch")
            st.caption(
                "Horizontal position uses the source's minute field; it is not a measured review duration."
            )
        show_table(timeline.drop(columns=["event_id"]))
    with evidence:
        st.subheader("Source evidence")
        index = st.selectbox(
            "Recorded event",
            timeline.index,
            format_func=lambda i: (
                f"{timeline.loc[i, 'event']} · record {timeline.loc[i, 'source_record_id']}"
            ),
        )
        provenance = service.provenance(timeline.loc[index, "source_record_id"])
        evidence_table = provenance.T.rename(columns={0: "Value"}).rename_axis("Field").reset_index()
        evidence_table["Value"] = evidence_table["Value"].astype("string")
        show_table(evidence_table)
    if timeline.minute.isna().any():
        st.info(
            "Some events have no known clock time. Their table rows remain visible without an invented time."
        )


@page("Referee Analytics")
def referees(service, scope):
    frame = service.referees(scope)
    st.caption(
        "Match-responsibility totals use main-referee appointments. They do not imply direct attribution of every event."
    )
    if not empty(frame):
        metric = st.selectbox("Compare", ["matches", "decisions", "penalties", "cards"])
        chart(frame, "referee", metric, f"Recorded {metric} by main referee")
        show_table(frame.drop(columns=["referee_id"]))


@page("VAR Analytics")
def var(service, scope):
    frame = service.reviews(scope)
    if empty(
        frame,
        "VAR data is unavailable in the current database. A provider with explicit review evidence is required.",
    ):
        return
    reviews = frame[frame.review_kind == "review"]
    known = reviews[reviews.outcome_code.isin(["UPHELD", "OVERTURNED"])]
    overturned = int((known.outcome_code == "OVERTURNED").sum())
    fraction = rate(overturned, len(known))
    cols = st.columns(4)
    cols[0].metric("Recorded reviews", len(reviews))
    cols[1].metric("Recorded checks", int((frame.review_kind == "check").sum()))
    cols[2].metric("Overturn rate", f"{fraction:.1%}" if fraction is not None else "Unavailable")
    cols[3].metric("Unknown review outcomes", len(reviews) - len(known))
    st.caption(
        f"Overturn denominator: {len(known)} reviews with recorded upheld/overturned outcomes. Checks are excluded."
    )
    measured = reviews.duration_seconds.dropna().astype(float)
    if measured.empty:
        st.info(
            "Review durations are unavailable. Event durations and event clock positions are not substitutes."
        )
    else:
        st.metric("Mean measured review duration", f"{measured.mean():.1f} seconds")
        st.caption(f"Measured duration n = {len(measured)}; missing = {len(reviews) - len(measured)}.")
    outcomes = (
        frame.assign(outcome=frame.outcome_code.fillna("Unavailable"))
        .groupby(["review_kind", "outcome"], dropna=False)
        .size()
        .reset_index(name="records")
    )
    chart(outcomes, "outcome", "records", "Recorded VAR outcomes", color="review_kind", barmode="group")
    show_table(frame)


@page("Team Analytics")
def teams(service, scope):
    frame = service.teams(scope)
    st.caption(
        "Team involvement follows the source record. These counts do not establish bias or decision correctness."
    )
    if not empty(frame):
        metric = st.selectbox("Compare", ["decisions", "penalties", "cards", "matches"])
        chart(frame, "team", metric, f"Recorded {metric} by team")
        show_table(frame)


@page("Added Time Analytics")
def added_time(service, scope):
    frame = service.added_time(scope)
    if empty(frame, "Announced added time is unavailable. Final event times are not an announcement source."):
        return
    chart(frame, "period_code", "mean_announced_minutes", "Mean announced minutes by period")
    st.caption(
        "This comparison uses the recorded minute component. Seconds coverage and sample sizes are shown below; "
        "unknown announcements are excluded, never treated as zero."
    )
    show_table(frame)


@page("Data Management")
def management(service, scope):
    session = st.session_state.get("admin_session")
    try:
        require_admin(session)
    except PermissionError:
        st.session_state.pop("admin_session", None)
        with st.form("administrator_sign_in", clear_on_submit=True):
            password = st.text_input("Administrator password", type="password")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            failures = st.session_state.get("auth_failures", 0)
            if failures >= 5:
                st.error("Too many failed attempts in this session. Restart the session before trying again.")
            else:
                authenticated = authenticate(password)
                if authenticated:
                    st.session_state["admin_session"] = authenticated
                    st.session_state["auth_failures"] = 0
                    st.rerun()
                else:
                    st.session_state["auth_failures"] = failures + 1
                    st.error("The administrator password was not accepted.")
        st.caption("Administrator sign-in and database permissions are enforced separately.")
        return
    st.success("Signed in as an application administrator.")
    if st.button("Sign out"):
        st.session_state.pop("admin_session", None)
        st.rerun()
    st.info(
        "The local StatsBomb demo is loaded through the validated import command. "
        "Additional provider uploads and manual edits are not available yet."
    )
    st.write("Import history and validation results are available on Data Quality and Methodology.")


@page("Data Quality and Methodology")
def quality(service, scope):
    st.subheader("Source and coverage")
    st.write(
        "This local demonstration uses StatsBomb Open Data for FIFA World Cup 2022. "
        "Source files are pinned to a recorded repository revision and verified by SHA-256 before import. "
        "Original observations and import results are retained locally. Raw source files are excluded from GitHub."
    )
    st.markdown(
        "[Data source and terms](https://github.com/hudl/open-data) · "
        "[Field mappings and limitations](https://github.com/L1k1th1508/VAR-ANALYSIS_DBMS/blob/main/docs/source_coverage.md)"
    )
    st.write(
        "Coverage: match scores, local kickoff clocks, named main referees, player lists, "
        "fouls, goal events, penalty shots and event-tagged player cards. Penalty shootout shots are excluded "
        "from decision totals. Player lists can include unused substitutes. Card counts use event records "
        "and do not duplicate the same cards from lineup summaries."
    )
    st.info(
        "Unavailable: explicit VAR outcomes, AVAR names, measured review durations and announced added time. "
        "Kickoff timezone and UTC instant remain unknown. A fuller licensed source is still needed for these fields."
    )
    st.write(
        "Unknown outcomes stay unknown. Rates use known eligible outcomes and show their denominators. "
        "Review durations require recorded timing. Announced added time is distinct from time actually played."
    )
    batches, rejected = service.quality()
    st.subheader("Import history")
    if not empty(batches, "No imports have been performed."):
        show_table(batches)
    st.subheader("Rejected records")
    if not empty(rejected, "No rejected import records are stored."):
        show_table(rejected)
    with st.expander("Referee materialized summary and freshness"):
        summary = service.materialized_summary()
        if not empty(
            summary,
            "The summary is empty. Refresh is an owner maintenance operation after an approved import.",
        ):
            show_table(summary)
    st.caption("The application does not independently judge decisions or claim to measure referee bias.")
