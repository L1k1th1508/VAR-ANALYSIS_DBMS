"""Fetch an explicitly supported pinned StatsBomb season into local, ignored storage."""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

REVISION = "4b73468fc5b0f1950f9f66fada70ad3a4f9327cb"
ROOT = Path(__file__).resolve().parents[1] / "data/raw/statsbomb"


def main():
    parser = argparse.ArgumentParser(description="Download a pinned source-backed demonstration season")
    parser.add_argument("--dataset", choices=["world-cup", "premier-league"], default="world-cup")
    args = parser.parse_args()
    competition, season = (2, 27) if args.dataset == "premier-league" else (43, 106)
    target_root = ROOT if competition == 43 else ROOT.parent / "statsbomb-premier-league"
    target_root.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=90, follow_redirects=True, transport=httpx.HTTPTransport(retries=3)) as client:

        def fetch(path):
            url = f"https://raw.githubusercontent.com/hudl/open-data/{REVISION}/{path}"
            target = target_root / path
            response = client.get(url)
            response.raise_for_status()
            content = response.content
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return path, {"url": url, "sha256": hashlib.sha256(content).hexdigest()}

        path, info = fetch(f"data/matches/{competition}/{season}.json")
        files = {path: info}
        matches = json.loads((target_root / path).read_bytes())
        if len(matches) != (380 if competition == 2 else 64):
            raise ValueError("Unexpected pinned season match count")
        paths = [f"data/{kind}/{m['match_id']}.json" for m in matches for kind in ("events", "lineups")]
        paths += ["README.md", "LICENSE.pdf"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for index, (path, info) in enumerate(pool.map(fetch, paths), 1):
                files[path] = info
                if index % 20 == 0:
                    print(f"Downloaded {index}/{len(paths)} source files", flush=True)
        manifest = {
            "provider": "StatsBomb Open Data",
            "revision": REVISION,
            "competition_id": competition,
            "season_id": season,
            "selected_match_ids": sorted(m["match_id"] for m in matches),
            "files": files,
        }
        (target_root / "demo_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Ready: {len(matches)} matches, {len(files)} checksummed files. Raw data stays local.")


if __name__ == "__main__":
    main()
