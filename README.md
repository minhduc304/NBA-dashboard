# NBA Stats Dashboard

## Quick Start

### Collect And Save All Active Players

```python
from nba_stats_collector import NBAStatsCollector

collector = NBAStatsCollector()
collector.collect_all_active_players()
```

### Collect And Save Stats For A Single Player
```python
from nba_stats_collector import NBAStatsCollector

collector = NBAStatsCollector()
collector.collect_and_save_player("Lebron James")
```

### Update Stats (Recommended for Daily Updates)

**Update all players (only those with new games):**
```bash
python update_stats.py
```

**Update specific player:**
```bash
python update_stats.py --player "Devin Booker"
```

**If rate limited, use:**
```bash
python python update_stats.py --include-new
```

### Verify Data

```bash
python verify_data.py
```

## Files

- `nba_stats_collector.py` - Main data collection module
- `update_stats.py` - Efficient update script (recommended for daily use)
- `verify_data.py` - Database verification script
- `nba_stats.db` - SQLite database (created after first run)

## Collected Stats

1. Points per game
2. Assists per game
3. Rebounds per game
4. Threes made per game
5. PTS+AST (calculated)
6. PTS+REB (calculated)
7. AST+REB (calculated)
8. PTS+AST+REB (calculated)
9. Double-doubles (total)
10. Triple-doubles (total)
11. Steals, Blocks, STL+BLK
12. Turnovers, Fouls, FT Attempted
13. Q1 Points, Q1 Assists, Q1 Rebounds
14. First Half Points

**All stats are per-game averages** (except double-doubles and triple-doubles which are totals).

## Database

SQLite database with table: `player_stats`

Query example:
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('nba_stats.db')
df = pd.read_sql_query("SELECT * FROM player_stats WHERE points > 25", conn)
conn.close()
```


## Dependencies

```bash
pip install nba_api
```
