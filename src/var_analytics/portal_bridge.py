"""Bounded JSON interface for the Next.js server; uses existing Python services."""

import json
import sys

from var_analytics.analytics_service import AnalyticsService, Scope
from var_analytics.auth import authenticate


def main():
    request = json.load(sys.stdin)
    if request.get("action") == "authenticate":
        print(json.dumps({"authenticated": authenticate(request.get("password", "")) is not None}))
        return
    service = AnalyticsService()
    scope = Scope.model_validate(request.get("scope", {}))
    catalog = service.catalog(scope)
    result = {
        "totals": json.loads(service.totals(scope).to_json()),
        "matches": json.loads(
            catalog.head(100).to_json(orient="records", date_format="iso", default_handler=str)
        ),
        "referees": json.loads(service.referees(scope).to_json(orient="records", default_handler=str)),
        "reviews": json.loads(service.reviews(scope).to_json(orient="records", default_handler=str)),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
