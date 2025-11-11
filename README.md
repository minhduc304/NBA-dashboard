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
# Basic update (includes shooting zones)
python update_stats.py

# Update specific player
python update_stats.py --player "Devin Booker"

# Update with assist zones (incremental, only processes new games)
python update_stats.py --collect-assist-zones --delay 0.6

# ONLY update team defensive zones (all 30 teams, skips player updates)
python update_stats.py --collect-team-defense --delay 0.6

# ONLY update play types (incremental, skips player updates)
python update_stats.py --collect-play-types --delay 1.0

# ONLY update both (skips player updates)
python update_stats.py --collect-team-defense --collect-play-types --delay 1.0

# Update EVERYTHING at once (recommended for daily updates)
python update_stats.py --collect-assist-zones --collect-team-defense --collect-play-types --delay 1.0

# Add new active players (including free agents)
python update_stats.py --include-new

# Skip free agents entirely (saves ~45 API calls)
python update_stats.py --rostered-only

# Add only new players not present in the DB (to continue collection)
python update_stats.py --add-new-only

# Add missing shooting zones data
python backfill_shooting_zones.py

# Combine arguments as needed
python update_stats.py --include-new --delay 2.0 --rostered-only
```

**If you get rate limited:**
```bash
# Stop the script (Ctrl+C) - progress is saved automatically!
# Resume with longer delay:
python update_stats.py --collect-assist-zones --collect-team-defense --delay 2.0

# Or run collections separately:
python update_stats.py --delay 1.0                         # Player stats only
python update_stats.py --collect-assist-zones --delay 1.5  # Assist zones only (heavy, includes player updates)
python update_stats.py --collect-team-defense --delay 0.6  # Team defense only (30 teams, quick)
python update_stats.py --collect-play-types --delay 1.0    # Play types only (incremental, skips player updates)
```

### Verify Data

```bash
python verify_data.py
```

## Files
- `nba_stats_collector.py` - Main data collection module
- `update_stats.py` - Efficient update script (recommended for daily use)
- `verify_data.py` - Database verification script
- `query_play_types.py` - Query and analyze play type statistics
- `nba_stats.db` - SQLite database (created after first run)
- `docs/PLAY_TYPES_GUIDE.md` - Complete play types documentation

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
1. **Player Shooting Zones** (6 zones)
   - Restricted Area, In The Paint (Non-RA), Mid-Range, Left Corner 3, Right Corner 3, Above the Break 3
   - Stores: FGM, FGA, FG%, eFG% per zone (per-game averages)

2. **Team Defensive Zones** (6 zones)
   - Shows opponent shooting efficiency by zone
   - Identifies defensive strengths/weaknesses
   - Stores: Opponent FGM, FGA, FG%, eFG% per zone (per-game averages)

### Assist Zones
3. **Player Assist Zones** (6 zones, same zones as above)
   - Tracks where a player's assists LEAD to made baskets
   - Example: Does Devin Booker's assists result in corner 3s or paint shots?
   - Stores: Assists, AST_FGM, AST_FGA per zone (totals)
   - Also stores: last_game_id, last_game_date, games_analyzed (embedded metadata for incremental updates)

### Play Types (Synergy)
4. **Player Play Types** (10 play types)
   - Isolation, Transition, Pick & Roll Ball Handler, Pick & Roll Roll Man, Post Up, Spot Up, Handoff, Cut, Off Screen, Putbacks
   - Shows **scoring breakdown** by play type (what % of points come from each play type)
   - Stores: Points, PPG, Possessions, Poss/G, PPP, FG%, % of Total Points
   - Example: Kevin Durant gets 22% from Spot Up, 19% from Isolation
   - Query with: `python query_play_types.py "Player Name"`

**All stats are per-game averages** (except double-doubles, triple-doubles, and assist zones which are totals).

## Database

SQLite database with tables: `player_stats`, `player_shooting_zones`, `team_defensive_zones`, `player_assist_zones`, `player_play_types`

### Query Examples
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

# View all player assist zones
df = pd.read_sql_query("SELECT * FROM player_assist_zones LIMIT 20", conn)
print(df)

# View specific player's assist zones with their name
df = pd.read_sql_query("""
    SELECT
        ps.player_name,
        paz.zone_name,
        paz.assists,
        paz.ast_fgm,
        paz.ast_fga,
        paz.games_analyzed,
        ROUND(CAST(paz.assists AS FLOAT) / paz.games_analyzed, 2) as assists_per_game
    FROM player_assist_zones paz
    JOIN player_stats ps ON paz.player_id = ps.player_id
    WHERE ps.player_name = 'Devin Booker'
    ORDER BY paz.assists DESC
""", conn)
print(df)
conn.close()

# Compare two players' assist zone distributions
df = pd.read_sql_query("""
    SELECT
        ps.player_name,
        paz.zone_name,
        paz.assists,
        paz.games_analyzed,
        ROUND(CAST(paz.assists AS FLOAT) / paz.games_analyzed, 2) as assists_per_game
    FROM player_assist_zones paz
    JOIN player_stats ps ON paz.player_id = ps.player_id
    WHERE ps.player_name IN ('Chris Paul', 'Luka Doncic')
    ORDER BY ps.player_name, paz.assists DESC
""", conn)
print(df)
conn.close()

# View player play types breakdown
df = pd.read_sql_query("""
    SELECT
        ps.player_name,
        ppt.play_type,
        ppt.points_per_game,
        ppt.pct_of_total_points,
        ppt.ppp,
        ppt.fg_pct
    FROM player_play_types ppt
    JOIN player_stats ps ON ppt.player_id = ps.player_id
    WHERE ps.player_name = 'Kevin Durant'
    ORDER BY ppt.points_per_game DESC
""", conn)
print(df)
conn.close()

# Or use the query script for formatted output:
# python query_play_types.py "Kevin Durant"
# python query_play_types.py --compare "Kevin Durant" "LeBron James"
# python query_play_types.py --top Isolation --limit 15
```


## Dependencies

```bash
pip install nba_api
```
