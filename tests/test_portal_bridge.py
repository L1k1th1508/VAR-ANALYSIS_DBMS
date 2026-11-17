"""The web bridge must serialize source UUIDs and missing values safely."""

import io
import json
from uuid import uuid4

import pandas as pd

from var_analytics import portal_bridge


def test_portal_serializes_uuid_and_unknown(monkeypatch, capsys):
    match_id = uuid4()

    class Service:
        def catalog(self, scope):
            return pd.DataFrame([{"match_id": match_id, "venue": None}])

        def totals(self, scope):
            return pd.Series({"matches": 1})

        def referees(self, scope):
            return pd.DataFrame()

        reviews = referees

    monkeypatch.setattr(portal_bridge, "AnalyticsService", Service)
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    portal_bridge.main()
    result = json.loads(capsys.readouterr().out)
    assert result["matches"] == [{"match_id": str(match_id), "venue": None}]
    assert result["totals"]["matches"] == 1
