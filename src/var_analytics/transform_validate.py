"""Explicit StatsBomb mappings; absence of VAR/announcement evidence stays unknown."""

from collections import defaultdict
from datetime import date, time
from uuid import NAMESPACE_URL, UUID, uuid5

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from var_analytics.extract import Snapshot

TRANSFORM_VERSION = "statsbomb-worldcup2022-v1"
TABLE_ORDER = [
    "country",
    "league",
    "season",
    "team",
    "venue",
    "referee",
    "player",
    "football_match",
    "match_official",
    "match_player",
    "decision",
    "decision_team",
    "card_issued",
]


def identity(kind, key):
    return uuid5(NAMESPACE_URL, f"https://statsbomb.com/open-data/{kind}/{key}")


class Named(BaseModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1)


class Match(BaseModel):
    match_id: int = Field(gt=0)
    match_date: date
    kick_off: time
    home_score: int = Field(ge=0)
    away_score: int = Field(ge=0)
    home_team: dict
    away_team: dict

    @model_validator(mode="after")
    def distinct_teams(self):
        if self.home_team["home_team_id"] == self.away_team["away_team_id"]:
            raise ValueError("Match participants must be different")
        return self


class Event(BaseModel):
    id: UUID
    index: int = Field(ge=0)
    period: int = Field(ge=1, le=5)
    minute: int = Field(ge=0)
    second: int = Field(ge=0, le=59)
    team: Named
    player: Named | None = None


class Player(BaseModel):
    player_id: int = Field(gt=0)
    player_name: str = Field(min_length=1)


class RecordValidationError(ValueError):
    def __init__(self, locator, reason):
        self.locator = locator
        self.reason = reason
        super().__init__(f"Source validation failed at {locator}: {reason}")


def transform(snapshot: Snapshot) -> dict[str, list[dict]]:
    rows = {name: {} for name in TABLE_ORDER}
    participants, members = {}, set()
    seen_events = set()
    lineup_teams = defaultdict(set)

    def put(table, key, locator, **values):
        rows[table][key] = {"source_record_id": locator, **values}

    def country(raw, locator):
        if not raw:
            return None
        item = Named.model_validate(raw)
        cid = identity("country", item.id)
        put("country", cid, locator, country_id=cid, name=item.name)
        return cid

    def entity(table, raw, locator):
        item = Named.model_validate(raw)
        eid = identity(table, item.id)
        put(
            table,
            eid,
            locator,
            **{f"{table}_id": eid},
            name=item.name,
            country_id=country(raw.get("country"), locator),
        )
        return eid

    for observation in snapshot.observations:
        raw, locator = observation["raw_payload"], observation["record_locator"]
        kind = observation["entity_kind"]
        try:
            if kind == "match":
                match = Match.model_validate(raw)
                if raw["match_status"] != "available":
                    raise ValueError("Expected completed match with available event data")
                mid = identity("match", match.match_id)
                league = identity("league", raw["competition"]["competition_id"])
                season = identity(
                    "season", f"{raw['competition']['competition_id']}/{raw['season']['season_id']}"
                )
                put(
                    "league",
                    league,
                    locator,
                    league_id=league,
                    name=raw["competition"]["competition_name"],
                    competition_kind="international",
                )
                put(
                    "season",
                    season,
                    locator,
                    season_id=season,
                    league_id=league,
                    label=raw["season"]["season_name"],
                )
                teams = []
                for side in ("home", "away"):
                    value = raw[f"{side}_team"]
                    teams.append(
                        entity(
                            "team",
                            {
                                "id": value[f"{side}_team_id"],
                                "name": value[f"{side}_team_name"],
                                "country": value.get("country"),
                            },
                            locator,
                        )
                    )
                participants[match.match_id] = set(teams)
                venue = entity("venue", raw["stadium"], locator) if raw.get("stadium") else None
                put(
                    "football_match",
                    mid,
                    locator,
                    match_id=mid,
                    season_id=season,
                    venue_id=venue,
                    home_team_id=teams[0],
                    away_team_id=teams[1],
                    status="completed",
                    home_score=match.home_score,
                    away_score=match.away_score,
                    match_date=match.match_date,
                    kickoff_local=match.kick_off,
                    kickoff_at=None,
                    timezone_name=None,
                )
                if raw.get("referee"):
                    referee = entity("referee", raw["referee"], locator)
                    put(
                        "match_official",
                        (mid, "MAIN_REFEREE", 1),
                        locator,
                        match_id=mid,
                        role_code="MAIN_REFEREE",
                        slot_no=1,
                        referee_id=referee,
                    )
            elif kind == "lineup":
                match_key = observation["match_id"]
                mid, tid = identity("match", match_key), identity("team", raw["team_id"])
                if tid not in participants[match_key]:
                    raise ValueError("Lineup team does not participate in match")
                lineup_teams[match_key].add(tid)
                frame = pd.json_normalize(raw["lineup"])
                if frame.empty or frame.player_id.duplicated().any():
                    raise ValueError("Empty lineup or duplicate lineup player IDs")
                for item in raw["lineup"]:
                    player = Player.model_validate(item)
                    pid = identity("player", player.player_id)
                    if (mid, pid) in members:
                        raise ValueError("Player appears more than once in match lineups")
                    members.add((mid, pid))
                    put(
                        "player",
                        pid,
                        locator,
                        player_id=pid,
                        name=player.player_name,
                        country_id=country(item.get("country"), locator),
                    )
                    put("match_player", (mid, pid), locator, match_id=mid, player_id=pid, team_id=tid)
            elif kind == "event":
                event = Event.model_validate(raw)
                if event.id in seen_events:
                    raise ValueError("Duplicate source event ID")
                seen_events.add(event.id)
                match_key = observation["match_id"]
                mid, tid = identity("match", match_key), identity("team", event.team.id)
                if tid not in participants[match_key]:
                    raise ValueError("Event team does not participate in match")
                clock = dict(
                    period_code=event.period,
                    minute=event.minute,
                    second=event.second,
                    source_order=event.index,
                )
                shot = raw.get("shot", {})
                event_type = raw["type"]["name"]
                decision_type, outcome = None, None
                if event.period != 5:
                    if event_type == "Foul Committed":
                        decision_type = "FOUL"
                    elif shot.get("type", {}).get("name") == "Penalty":
                        decision_type = "PENALTY"
                        outcome = "GOAL" if shot.get("outcome", {}).get("name") == "Goal" else None
                    elif shot.get("outcome", {}).get("name") == "Goal" or event_type == "Own Goal Against":
                        decision_type, outcome = "GOAL", "GOAL"
                if decision_type:
                    did = identity("decision", event.id)
                    description = event_type + (f" — {event.player.name}" if event.player else "")
                    if raw.get("foul_committed", {}).get("advantage"):
                        description += " (advantage recorded)"
                    put(
                        "decision",
                        did,
                        locator,
                        decision_id=did,
                        match_id=mid,
                        decision_type_code=decision_type,
                        outcome_code=outcome,
                        description=description,
                        **clock,
                    )
                    put(
                        "decision_team",
                        (did, tid),
                        locator,
                        decision_id=did,
                        team_id=tid,
                        involvement_code="recorded_team",
                    )
                card = raw.get("foul_committed", {}).get("card") or raw.get("bad_behaviour", {}).get("card")
                if card:
                    if event.player is None:
                        raise ValueError("Card has no recorded player")
                    pid = identity("player", event.player.id)
                    if (mid, pid) not in members or rows["match_player"][(mid, pid)]["team_id"] != tid:
                        raise ValueError("Card player/team does not match lineup")
                    card_type = {
                        "Yellow Card": "yellow",
                        "Second Yellow": "second_yellow",
                        "Red Card": "red",
                    }[card["name"]]
                    cid = identity("card", event.id)
                    put(
                        "card_issued",
                        cid,
                        locator,
                        card_id=cid,
                        match_id=mid,
                        player_id=pid,
                        card_type=card_type,
                        **clock,
                    )
            else:
                raise ValueError("Unsupported observation kind")
        except (ValueError, KeyError, TypeError) as exc:
            raise RecordValidationError(locator, str(exc)) from exc
    for match_key, teams in participants.items():
        if lineup_teams[match_key] != teams:
            raise RecordValidationError(str(match_key), "Both match lineups are required")
    return {name: list(values.values()) for name, values in rows.items()}
