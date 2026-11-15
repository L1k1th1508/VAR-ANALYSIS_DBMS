import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from var_analytics.db import engine_for
from var_analytics.extract import extract
from var_analytics.load import load_snapshot
from var_analytics.migrate import migrate, refresh
from var_analytics.supplements import extract_evidence, import_evidence, import_premier_added_time


def main() -> None:
    parser = argparse.ArgumentParser(description="Owner maintenance and source-backed imports")
    parser.add_argument(
        "command",
        choices=[
            "migrate",
            "refresh",
            "import-demo",
            "import-evidence",
            "import-premier-league",
            "import-premier-added-time",
        ],
    )
    parser.add_argument(
        "--evidence-file", type=Path, default=Path("data/supplements/world_cup_2022_evidence.json")
    )
    parser.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--test", action="store_true", help="Use the isolated test database")
    args = parser.parse_args()
    load_dotenv()
    prefix = "TEST_" if args.test else ""
    if args.command == "migrate":
        print("Applied:", migrate(os.environ[f"{prefix}OWNER_DATABASE_URL"]))
    elif args.command == "refresh":
        refresh(os.environ[f"{prefix}OWNER_DATABASE_URL"])
        print("Referee summary refreshed.")
    elif args.command in {"import-demo", "import-premier-league"}:
        premier = args.command == "import-premier-league"
        folder = args.source_dir or Path(
            "data/raw/statsbomb-premier-league" if premier else "data/raw/statsbomb"
        )
        snapshot = extract(folder, expected_scope=(2, 27) if premier else (43, 106))
        result = load_snapshot(
            engine_for(os.environ[f"{prefix}ADMIN_DATABASE_URL"]),
            snapshot,
            transform_version="statsbomb-premierleague2015-v1" if premier else None,
        )
        refresh(os.environ[f"{prefix}OWNER_DATABASE_URL"])
        print(result)
    elif args.command == "import-evidence":
        result = import_evidence(
            engine_for(os.environ[f"{prefix}ADMIN_DATABASE_URL"]), extract_evidence(args.evidence_file)
        )
        refresh(os.environ[f"{prefix}OWNER_DATABASE_URL"])
        print(result)
    elif args.command == "import-premier-added-time":
        result = import_premier_added_time(
            engine_for(os.environ[f"{prefix}ADMIN_DATABASE_URL"]),
            extract_evidence(Path("data/supplements/premier_league_2015_added_time.json")),
        )
        refresh(os.environ[f"{prefix}OWNER_DATABASE_URL"])
        print(result)


if __name__ == "__main__":
    main()
