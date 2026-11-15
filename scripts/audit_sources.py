"""Download a pinned, real source sample into ignored storage and audit field coverage."""

import hashlib
import json
from pathlib import Path

import httpx
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    target = ROOT / "data" / "raw" / "statsbomb"
    target.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        revision = "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
        files = {}

        def fetch(path: str) -> bytes:
            url = f"https://raw.githubusercontent.com/statsbomb/open-data/{revision}/{path}"
            r = client.get(url)
            r.raise_for_status()
            local = target / path
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(r.content)
            files[path] = {"url": url, "sha256": hashlib.sha256(r.content).hexdigest()}
            return r.content

        fetch("README.md")
        fetch("LICENSE.pdf")
        fetch("doc/Open Data Matches v3.0.0.pdf")
        fetch("doc/Open Data Events v4.0.0.pdf")
        matches = json.loads(fetch("data/matches/43/106.json"))
        chosen = sorted(matches, key=lambda m: (m["match_date"], m["match_id"]))[-3:]
        summaries = []
        for match in chosen:
            mid = match["match_id"]
            events = json.loads(fetch(f"data/events/{mid}.json"))
            lineups = json.loads(fetch(f"data/lineups/{mid}.json"))
            types = {}
            card_count = 0
            for event in events:
                name = event["type"]["name"]
                types[name] = types.get(name, 0) + 1
                card_count += bool(
                    event.get("foul_committed", {}).get("card") or event.get("bad_behaviour", {}).get("card")
                )
            summaries.append(
                {
                    "match_id": mid,
                    "home": match["home_team"]["home_team_name"],
                    "away": match["away_team"]["away_team_name"],
                    "date": match["match_date"],
                    "score": [match["home_score"], match["away_score"]],
                    "referee": match.get("referee"),
                    "events": len(events),
                    "cards": card_count,
                    "event_types": types,
                    "lineup_players": sum(len(t["lineup"]) for t in lineups),
                    "var_named_events": sum(v for k, v in types.items() if "var" in k.lower()),
                    "match_keys": sorted(match),
                }
            )
        manifest = {
            "provider": "StatsBomb Open Data",
            "revision": revision,
            "competition_id": 43,
            "season_id": 106,
            "selected_match_ids": [m["match_id"] for m in chosen],
            "files": files,
            "sample": summaries,
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        for name in ["LICENSE.pdf", "doc/Open Data Matches v3.0.0.pdf", "doc/Open Data Events v4.0.0.pdf"]:
            reader = PdfReader(target / name)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            (target / (Path(name).stem + ".txt")).write_text(text, encoding="utf-8")
        print(json.dumps({"revision": revision, "sample": summaries}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
