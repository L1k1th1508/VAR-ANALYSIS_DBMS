import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from var_analytics.db import engine_for
from var_analytics.extract import extract
from var_analytics.load import load_snapshot
from var_analytics.migrate import migrate, refresh


def main() -> None:
    parser = argparse.ArgumentParser(description="Owner maintenance and source-backed imports")
    parser.add_argument("command", choices=["migrate", "refresh", "import-demo"])
    parser.add_argument("--source-dir", type=Path, default=Path("data/raw/statsbomb"))
    parser.add_argument("--test", action="store_true", help="Use the isolated test database")
    args = parser.parse_args()
    load_dotenv()
    prefix = "TEST_" if args.test else ""
    if args.command == "migrate":
        print("Applied:", migrate(os.environ[f"{prefix}OWNER_DATABASE_URL"]))
    elif args.command == "refresh":
        refresh(os.environ[f"{prefix}OWNER_DATABASE_URL"])
        print("Referee summary refreshed.")
    elif args.command == "import-demo":
        snapshot = extract(args.source_dir)
        result = load_snapshot(engine_for(os.environ[f"{prefix}ADMIN_DATABASE_URL"]), snapshot)
        refresh(os.environ[f"{prefix}OWNER_DATABASE_URL"])
        print(result)


if __name__ == "__main__":
    main()
