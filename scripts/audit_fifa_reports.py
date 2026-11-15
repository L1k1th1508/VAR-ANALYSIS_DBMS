"""Inspect FIFA reports locally; do not use their Additional time field as board announcements.

Some values differ from the original announcement (e.g. England-Iran second half).
This is a research audit only: no database import and no PDF redistribution.
"""

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1] / "data/raw/fifa"


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, transport=httpx.HTTPTransport(retries=2)) as client:

        def fetch(number):
            report = f"r{number}"
            url = f"https://fdp.fifa.org/assetspublic/ce44/{report}/pdf/FullTimeMatchReport-English.pdf"
            target = ROOT / f"{report}.pdf"
            if not target.exists():
                response = client.get(url)
                response.raise_for_status()
                target.write_bytes(response.content)
            reader = PdfReader(target)
            pages = [p.extract_text(extraction_mode="layout") for p in reader.pages]
            (ROOT / f"{report}.txt").write_text("\n\f\n".join(pages), encoding="utf-8")
            plain = reader.pages[0].extract_text()
            header = next(line.strip() for line in plain.splitlines() if "v." in line)
            match_number = re.search(r"#(\d+)", plain).group(1)
            dates = re.findall(r"\d{1,2} \w+ 2022", plain)
            added = []
            for page_no, page in enumerate(pages, 1):
                for line in page.splitlines():
                    if "Additional time:" in line:
                        added.append({"page": page_no, "line": line.strip()})
            return {
                "report": report,
                "url": url,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "header": header,
                "match_number": int(match_number),
                "date": dates[0],
                "added_time": added,
            }

        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(fetch, range(2801, 2865)))
        (ROOT / "audit.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        for item in records:
            print(item["report"], item["match_number"], item["header"], item["date"], item["added_time"])
        print("Reports:", len(records), "period lines:", sum(len(r["added_time"]) for r in records))


if __name__ == "__main__":
    main()
