from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from var_analytics.analytics_service import AnalyticsService, Scope, rate


def test_rate_excludes_empty_denominator():
    assert rate(0, 0) is None
    assert rate(1, 2) == 0.5
    assert rate(0, 2) == 0
    with pytest.raises(ValueError):
        rate(3, 2)


def test_scope_is_typed_and_dates_ordered():
    with pytest.raises(ValidationError):
        Scope(league_id="';DROP SCHEMA var CASCADE;--")
    with pytest.raises(ValidationError):
        Scope(from_date=date(2022, 12, 18), to_date=date(2022, 12, 1))


@pytest.mark.integration
def test_analytical_queries_on_source_backed_schema_fixture(owner, source_case):
    service = AnalyticsService(owner)
    catalog = service.catalog(Scope())
    assert len(catalog) == 3
    totals = service.totals(Scope())
    assert totals.matches == 3 and totals.decisions == 1 and totals.reviews == 0
    refs = service.referees(Scope())
    assert refs.matches.sum() == 3 and refs.decisions.sum() == 1
    assert "match_rank" in refs
    teams = service.teams(Scope())
    assert teams.matches.sum() == 6 and teams.decisions.sum() == 1
    assert service.reviews(Scope()).empty
    assert service.added_time(Scope()).empty
    assert service.catalog(Scope(league_id=uuid4())).empty
    assert service.catalog(Scope(from_date=date(2000, 1, 1), to_date=date(2000, 1, 2))).empty
    match = source_case["matches"][0]["match"]
    assert len(service.officials(match)) == 1
    assert len(service.timeline(match)) == 1
    assert len(service.provenance(source_case["record"])) == 1
    batches, rejected = service.quality()
    assert len(batches) == 1 and rejected.empty
