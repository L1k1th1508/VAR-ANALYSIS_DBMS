"""Parameterized analytical queries; no provider-specific field assumptions."""

from datetime import date
from uuid import UUID

import pandas as pd
from pydantic import BaseModel, model_validator
from sqlalchemy import text

from var_analytics.db import reader_engine


class Scope(BaseModel):
    league_id: UUID | None = None
    season_id: UUID | None = None
    from_date: date | None = None
    to_date: date | None = None

    @model_validator(mode="after")
    def dates_ordered(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("Start date must be on or before end date")
        return self

    def filter(self):
        clauses, params = [], {}
        for name, column, operator in [
            ("league_id", "m.league_id", "="),
            ("season_id", "m.season_id", "="),
            ("from_date", "m.match_date", ">="),
            ("to_date", "m.match_date", "<="),
        ]:
            value = getattr(self, name)
            if value is not None:
                clauses.append(f"{column} {operator} :{name}")
                params[name] = value
        return " AND ".join(clauses) or "true", params


def rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    if not 0 <= numerator <= denominator:
        raise ValueError("Rate counts must satisfy 0 <= numerator <= denominator")
    return numerator / denominator


class AnalyticsService:
    def __init__(self, bind=None):
        self.bind = bind if bind is not None else reader_engine()

    def query(self, sql: str, params=None) -> pd.DataFrame:
        return pd.read_sql_query(text(sql), self.bind, params=params or {})

    def scoped(self, scope: Scope, sql: str):
        predicate, params = scope.filter()
        return self.query(
            f"WITH scoped AS (SELECT * FROM var.v_match_catalog m WHERE {predicate}) {sql}", params
        )

    def catalog(self, scope: Scope):
        return self.scoped(
            scope, "SELECT * FROM scoped ORDER BY match_date NULLS LAST,kickoff_local NULLS LAST"
        )

    def totals(self, scope: Scope):
        return self.scoped(
            scope,
            """
        SELECT (SELECT count(*) FROM scoped) matches,
          (SELECT count(*) FROM (SELECT home_team_id FROM scoped UNION SELECT away_team_id FROM scoped) t) teams,
          (SELECT count(DISTINCT referee_id) FROM var.match_official JOIN scoped USING(match_id)) referees,
          (SELECT count(*) FROM var.decision JOIN scoped USING(match_id)) decisions,
          (SELECT count(*) FROM var.var_involvement v JOIN var.decision d USING(decision_id)
           JOIN scoped m ON m.match_id=d.match_id WHERE review_kind='review') reviews
        """,
        ).iloc[0]

    def officials(self, match_id):
        return self.query(
            """SELECT r.name referee,role.label role,mo.slot_no,mo.source_record_id
          FROM var.match_official mo JOIN var.referee r USING(referee_id)
          JOIN var.official_role role USING(role_code) WHERE match_id=:id ORDER BY mo.role_code,mo.slot_no""",
            {"id": match_id},
        )

    def timeline(self, match_id):
        return self.query(
            """
          SELECT d.decision_id::text event_id,t.label event,d.period_code,d.minute,d.second,d.source_order,
                 d.description,d.source_record_id FROM var.decision d JOIN var.decision_type t USING(decision_type_code)
          WHERE match_id=:id
          UNION ALL
          SELECT c.card_id::text,c.card_type||' card',c.period_code,c.minute,c.second,c.source_order,
                 p.name,c.source_record_id FROM var.card_issued c JOIN var.player p USING(player_id) WHERE match_id=:id
          UNION ALL
          SELECT v.var_involvement_id::text,'VAR '||v.review_kind,v.period_code,v.minute,v.second,v.source_order,
                 coalesce(o.label,'Outcome unavailable'),v.source_record_id
          FROM var.var_involvement v JOIN var.decision d USING(decision_id)
          LEFT JOIN var.decision_outcome o ON o.outcome_code=v.outcome_code WHERE d.match_id=:id
          ORDER BY period_code NULLS LAST,minute NULLS LAST,second NULLS LAST,source_order NULLS LAST,event_id
        """,
            {"id": match_id},
        )

    def referees(self, scope: Scope):
        return self.scoped(
            scope,
            """, dc AS (
            SELECT match_id,count(*) decisions,count(*) FILTER(WHERE decision_type_code='PENALTY') penalties
            FROM var.decision GROUP BY match_id
        ), cc AS (SELECT match_id,count(*) cards FROM var.card_issued GROUP BY match_id), summary AS (
            SELECT mo.referee_id,r.name referee,count(*) matches,sum(coalesce(dc.decisions,0)) decisions,
                sum(coalesce(dc.penalties,0)) penalties,sum(coalesce(cc.cards,0)) cards
            FROM scoped m JOIN var.match_official mo USING(match_id) JOIN var.referee r USING(referee_id)
            LEFT JOIN dc USING(match_id) LEFT JOIN cc USING(match_id)
            WHERE mo.role_code='MAIN_REFEREE' GROUP BY mo.referee_id,r.name
        ) SELECT *,dense_rank() OVER(ORDER BY matches DESC) match_rank FROM summary ORDER BY matches DESC,referee
        """,
        )

    def reviews(self, scope: Scope):
        return self.scoped(
            scope,
            """SELECT v.var_involvement_id,v.review_kind,v.outcome_code,v.duration_seconds,
            m.match_id,m.home_team,m.away_team,m.match_date FROM var.var_involvement v
            JOIN var.decision d USING(decision_id) JOIN scoped m ON m.match_id=d.match_id""",
        )

    def teams(self, scope: Scope):
        return self.scoped(
            scope,
            """, teams AS (
            SELECT home_team_id team_id,match_id FROM scoped UNION ALL SELECT away_team_id,match_id FROM scoped
        ), appearances AS (SELECT team_id,count(*) matches FROM teams GROUP BY team_id), dc AS (
            SELECT dt.team_id,count(*) decisions,count(*) FILTER(WHERE d.decision_type_code='PENALTY') penalties
            FROM var.decision_team dt JOIN var.decision d USING(decision_id) JOIN scoped USING(match_id)
            GROUP BY dt.team_id
        ), cc AS (
            SELECT mp.team_id,count(*) cards FROM var.card_issued c JOIN var.match_player mp USING(match_id,player_id)
            JOIN scoped USING(match_id) GROUP BY mp.team_id
        ) SELECT t.name team,a.matches,coalesce(dc.decisions,0) decisions,
            coalesce(dc.penalties,0) penalties,coalesce(cc.cards,0) cards
        FROM appearances a JOIN var.team t USING(team_id) LEFT JOIN dc USING(team_id) LEFT JOIN cc USING(team_id)
        ORDER BY t.name""",
        )

    def added_time(self, scope: Scope):
        return self.scoped(
            scope,
            """SELECT a.period_code,count(*) announcements,
            avg(a.announced_minutes) mean_announced_minutes,
            count(a.announced_seconds) measured_seconds_n
            FROM var.added_time a JOIN scoped USING(match_id) GROUP BY a.period_code ORDER BY a.period_code""",
        )

    def provenance(self, source_record_id):
        return self.query(
            "SELECT * FROM var.v_source_provenance WHERE source_record_id=:id", {"id": int(source_record_id)}
        )

    def quality(self):
        return self.query("SELECT * FROM var.v_import_quality ORDER BY started_at DESC"), self.query(
            "SELECT * FROM var.v_record_quality WHERE validation_status='rejected' ORDER BY source_record_id DESC LIMIT 200"
        )

    def materialized_summary(self):
        return self.query("SELECT * FROM var.mv_referee_stat_summary ORDER BY matches DESC")
