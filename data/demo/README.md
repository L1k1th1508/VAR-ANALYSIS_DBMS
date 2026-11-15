# Offline demonstration status

Premier League 2015/16 is also supported: run `python scripts/fetch_demo.py --dataset premier-league` and `python -m var_analytics.cli import-premier-league`. This adds 380 real matches alongside World Cup 2022. Raw files remain ignored in `data/raw/statsbomb-premier-league`. Select the league/season in the dashboard. VAR was not in use in this season; three verified announced-time periods can be loaded with `python -m var_analytics.cli import-premier-added-time`.

No football dataset is distributed here. Following the user's request to populate the dashboard, the local demo uses verified StatsBomb World Cup 2022 records. Download them directly with `python scripts/fetch_demo.py`, then run `python -m var_analytics.cli import-demo`. Source files and their manifest stay in ignored `data/raw/statsbomb`; do not commit or bake them into the application image.

Then run `python -m var_analytics.cli import-evidence` to load the included cited factual supplement: six selected VAR reviews and 15 announced-time records across seven matches. Once preloaded, the persistent PostgreSQL database supports offline viewing without an API key; external source links need internet access. See [source coverage](../../docs/source_coverage.md). Broader coverage, AVAR identities and measured review durations still require further evidence.
