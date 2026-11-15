# Offline demonstration status

No football dataset is distributed here. Following the user's request to populate the dashboard, the local demo uses verified StatsBomb World Cup 2022 records. Download them directly with `python scripts/fetch_demo.py`, then run `python -m var_analytics.cli import-demo`. Source files and their manifest stay in ignored `data/raw/statsbomb`; do not commit or bake them into the application image.

Once preloaded, the persistent PostgreSQL database supports offline viewing without an API key. See [source coverage](../../docs/source_coverage.md). A fuller licensed source is still needed for VAR outcomes, AVAR names, review durations and announced added time. These fields remain unavailable.
