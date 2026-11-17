"""Read-only smoke check of the running local demo and all eight populated pages."""

import argparse
from pathlib import Path

import httpx
from dotenv import load_dotenv
from streamlit.testing.v1 import AppTest

from var_analytics.analytics_service import AnalyticsService, Scope
from var_analytics.transform_validate import identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8501, help="local Streamlit port (default: 8501)")
    parser.add_argument("--with-premier-league", action="store_true")
    parser.add_argument(
        "--with-world-cup-var", action="store_true", help="verify all 27 cited World Cup interventions"
    )
    parser.add_argument(
        "--with-premier-added-time",
        action="store_true",
        help="verify the Premier League season and its announced-time supplement",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    check_premier_league = args.with_premier_league or args.with_premier_added_time
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    response = httpx.get(f"http://127.0.0.1:{args.port}/_stcore/health", timeout=10)
    response.raise_for_status()
    assert response.text == "ok"
    service = AnalyticsService()
    world_cup = Scope(league_id=identity("league", 43), season_id=identity("season", "43/106"))
    totals = service.totals(world_cup)
    assert int(totals.matches) == 64 and int(totals.teams) == 32
    assert int(totals.decisions) == (1966 if args.with_world_cup_var else 1956)
    assert int(totals.referees) == 29
    assert int(totals.reviews) == (27 if args.with_world_cup_var else 6)
    if args.with_world_cup_var:
        assert service.reviews(world_cup).outcome_code.value_counts().to_dict() == {
            "OVERTURNED": 25,
            "UPHELD": 2,
        }
    assert len(service.added_time_records(world_cup)) == 15
    assert int(service.teams(world_cup).cards.sum()) == 228
    if check_premier_league:
        premier = Scope(league_id=identity("league", 2), season_id=identity("season", "2/27"))
        premier_totals = service.totals(premier)
        assert int(premier_totals.matches) == 380
        assert int(premier_totals.teams) == 20
        assert int(service.referees(premier).matches.sum()) == 380
        assert service.reviews(premier).empty
        print("Premier League totals:", {k: int(v) for k, v in premier_totals.items()})
        if args.with_premier_added_time:
            assert len(service.added_time_records(premier)) == 3
            means = service.added_time(premier).set_index("period_code")
            assert means.loc[1, "mean_announced_minutes"] == 2
            assert means.loc[2, "mean_announced_minutes"] == 5
    root_app = AppTest.from_file(str(root / "app.py")).run(timeout=30)
    assert not root_app.exception and not root_app.error
    assert root_app.metric[0].value == str(int(service.totals(Scope()).matches))
    root_app.selectbox[0].select(identity("league", 43)).run(timeout=30)
    assert not root_app.exception and not root_app.error
    assert root_app.selectbox[1].options == ["2022"]
    assert root_app.metric[0].value == "64"
    if check_premier_league:
        root_app.selectbox[0].select(identity("league", 2)).run(timeout=30)
        assert not root_app.exception and not root_app.error
        assert int(root_app.metric[0].value) >= 380
    for name in ("home", "matches", "referees", "var", "teams", "added_time", "management", "quality"):
        page = AppTest.from_string(f"from var_analytics.ui.pages import {name}\n{name}()").run(timeout=30)
        assert not page.exception and not page.error, name
        print(f"Page passed: {name}", flush=True)
    print("Healthy local demo:", {k: int(v) for k, v in totals.items()})


if __name__ == "__main__":
    main()
