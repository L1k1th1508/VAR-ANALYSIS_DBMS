"""Read checksummed local StatsBomb files; raw payloads never leave the local database."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Snapshot:
    fingerprint: str
    revision: str
    observations: list[dict]


def mapped_event(event: dict) -> bool:
    shot = event.get("shot", {})
    card = event.get("foul_committed", {}).get("card") or event.get("bad_behaviour", {}).get("card")
    return bool(card) or (
        event.get("period") != 5
        and (
            event.get("type", {}).get("name") in ("Foul Committed", "Own Goal Against")
            or shot.get("type", {}).get("name") == "Penalty"
            or shot.get("outcome", {}).get("name") == "Goal"
        )
    )


def extract(folder: Path, manifest_name: str = "demo_manifest.json") -> Snapshot:
    folder = folder.resolve()
    manifest = json.loads((folder / manifest_name).read_bytes())
    if manifest["competition_id"] != 43 or manifest["season_id"] != 106:
        raise ValueError("This adapter is audited for World Cup 2022 only")
    revision = manifest["revision"]
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("Expected a pinned source commit")
    observations = []
    hashes = {}

    def read(path):
        content = (folder / path).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != manifest["files"][path]["sha256"]:
            raise ValueError(f"Source checksum mismatch: {path}")
        hashes[path] = digest
        return json.loads(content)

    def capture(kind, key, path, raw, **context):
        observations.append(
            {
                "entity_kind": kind,
                "external_key": str(key),
                "record_locator": f"https://github.com/hudl/open-data/blob/{revision}/{path}#{key}",
                "raw_payload": raw,
                **context,
            }
        )

    path = "data/matches/43/106.json"
    matches = read(path)
    selected = set(manifest["selected_match_ids"])
    if not selected or not selected.issubset({m["match_id"] for m in matches}):
        raise ValueError("Manifest contains an unknown match or an empty scope")
    for match in sorted(matches, key=lambda m: m["match_id"]):
        mid = match["match_id"]
        if mid not in selected:
            continue
        capture("match", mid, path, match)
        lineup_path = f"data/lineups/{mid}.json"
        for team in read(lineup_path):
            capture("lineup", team["team_id"], lineup_path, team, match_id=mid)
        event_path = f"data/events/{mid}.json"
        for event in read(event_path):
            if mapped_event(event):
                capture("event", event["id"], event_path, event, match_id=mid)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "revision": revision,
                "selected": sorted(selected),
                "files": hashes,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return Snapshot(fingerprint, revision, observations)
