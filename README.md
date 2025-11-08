# NBA Stats Dashboard

## Usage Examples

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

### Update Player Stats (Recommended for Daily Updates)

**Update all players (only those with new games):**
```bash
python update_stats.py # Includes shooting zones 

# Update specific player
python update_stats.py --player "Devin Booker"

# To add new active players (including free agents)
python python update_stats.py --include-new

# To skip free agents entirely (and save api calls):
python python update_stats.py --rostered-only

# To add only new players not present in the DB (to continue data collection)
python update_stats.py --add-new-only

# Combine arguments as needed
python update_stats.py --include-new --delay 2.0 --rostered-only  
```

### Update Team Stats

**Collecting defensive shooting zones:**
```bash
# Single Team
collector.collect_and_save_team_defense("Phoenix Suns")
# All 30 teams 
collector.collect_all_team_defenses()  
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
### Basic stats
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

### Shooting Zones
1. Player Shooting Zones (6 zones)
  - Restricted Area, In The Paint, Mid-Range, Left Corner 3 Right Corner 3, Above the Break 3
  - Stores: FGM, FGA, FG%, eFG% per zone

2. Team Defensive Zones (6 zones)
  - Shows opponent shooting efficiency by zone
  - Identifies defensive strengths/weaknesses
  - Stores: Opponent FGM, FGA, FG%, eFG% per zone

**All stats are per-game averages** (except double-doubles and triple-doubles which are totals).

## Database

SQLite database with table: `player_stats`, `player_shooting_zones`, `team_defensive_zones`

Query example:
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('nba_stats.db')
df = pd.read_sql_query("SELECT * FROM player_stats WHERE points > 25", conn)
conn.close()


# View all player shooting zones
df = pd.read_sql_query("SELECT * FROM player_shooting_zones LIMIT 20", conn)
print(df)

# View specific player with their name
df = pd.read_sql_query("""
    SELECT 
        ps.player_name,
        psz.zone_name, 
        psz.fgm, 
        psz.fga, 
        psz.fg_pct, 
        psz.efg_pct
    FROM player_shooting_zones psz
    JOIN player_stats ps ON psz.player_id = ps.player_id
    WHERE ps.player_name = 'Devin Booker'
    ORDER BY psz.zone_name
""", conn)
print(df)
conn.close()

# View all team defensive zones
df = pd.read_sql_query("SELECT * FROM team_defensive_zones", conn)
print(df)

# View specific team (Phoenix Suns = 1610612756)
df = pd.read_sql_query("""
    SELECT zone_name, opp_fgm, opp_fga, opp_fg_pct, opp_efg_pct
    FROM team_defensive_zones
    WHERE team_id = 1610612756
    ORDER BY zone_name
""", conn)
print(df)
conn.close()
```


## Dependencies

```bash
pip install nba_api
```
