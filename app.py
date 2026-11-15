"""Eight-page native Streamlit dashboard with source-backed local demonstration data."""

from pathlib import Path

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from var_analytics.analytics_service import AnalyticsService, Scope
from var_analytics.ui import pages

st.set_page_config(page_title="Referee & VAR Decision Analytics", layout="wide")
st.markdown(
    """<style>
    h1,h2,h3 {font-family:'Barlow Condensed','Arial Narrow',sans-serif;font-weight:600;}
    h1 {letter-spacing:-.025em;}
    .stMainBlockContainer {max-width:1440px;padding-top:2.5rem;}
    [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums;}
    button:focus-visible,a:focus-visible {outline:3px solid #236FA1;outline-offset:3px;}
    @media (prefers-reduced-motion:reduce) {*{animation:none!important;transition:none!important;}}
    </style>""",
    unsafe_allow_html=True,
)
with st.sidebar:
    st.header("Referee & VAR")
    st.caption("Decision analytics and source evidence")
    st.markdown("Data: [StatsBomb Open Data](https://github.com/hudl/open-data)")
    logo = Path(__file__).resolve().parent / "assets/statsbomb-logo.png"
    if logo.exists():
        st.image(str(logo), width=170)
    try:
        catalog = AnalyticsService().catalog(Scope())
        league_names = dict(zip(catalog.league_id, catalog.league))
        league = st.selectbox(
            "League", [None, *league_names], format_func=lambda k: league_names.get(k, "All leagues")
        )
        seasons = catalog if league is None else catalog[catalog.league_id == league]
        season_names = dict(zip(seasons.season_id, seasons.season))
        season = st.selectbox(
            "Season", [None, *season_names], format_func=lambda k: season_names.get(k, "All seasons")
        )
        dates = st.date_input("Date range", value=())
        st.session_state["scope"] = Scope(
            league_id=league,
            season_id=season,
            from_date=dates[0] if len(dates) == 2 else None,
            to_date=dates[1] if len(dates) == 2 else None,
        )
        if len(dates) == 1:
            st.caption("Select the end date to apply the date filter.")
    except SQLAlchemyError:
        st.info("Start the database and apply migrations to enable filters.")

navigation = st.navigation(
    [
        st.Page(pages.home, title="Home Dashboard", default=True),
        st.Page(pages.matches, title="Match Explorer"),
        st.Page(pages.referees, title="Referee Analytics"),
        st.Page(pages.var, title="VAR Analytics"),
        st.Page(pages.teams, title="Team Analytics"),
        st.Page(pages.added_time, title="Added Time Analytics"),
        st.Page(pages.management, title="Data Management"),
        st.Page(pages.quality, title="Data Quality and Methodology"),
    ]
)
navigation.run()
