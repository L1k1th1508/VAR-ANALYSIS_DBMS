"""Read-only smoke check of the running local demo and all eight populated pages."""

from pathlib import Path

import httpx
from dotenv import load_dotenv
from streamlit.testing.v1 import AppTest

from var_analytics.analytics_service import AnalyticsService, Scope


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    response = httpx.get("http://127.0.0.1:8501/_stcore/health", timeout=10)
    response.raise_for_status()
    assert response.text == "ok"
    service = AnalyticsService()
    totals = service.totals(Scope())
    assert int(totals.matches) == 64 and int(totals.teams) == 32
    assert int(totals.decisions) == 1953 and int(totals.referees) == 29
    assert int(service.teams(Scope()).cards.sum()) == 228
    root_app = AppTest.from_file(str(root / "app.py")).run(timeout=30)
    assert not root_app.exception and not root_app.error
    assert root_app.metric[0].value == "64"
    for name in ("home", "matches", "referees", "var", "teams", "added_time", "management", "quality"):
        page = AppTest.from_string(f"from var_analytics.ui.pages import {name}\n{name}()").run(timeout=30)
        assert not page.exception and not page.error, name
        print(f"Page passed: {name}", flush=True)
    print("Healthy local demo:", {k: int(v) for k, v in totals.items()})


if __name__ == "__main__":
    main()
