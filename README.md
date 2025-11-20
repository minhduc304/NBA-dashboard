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
# Since play type collection uses a different from the NBA, sometimes its data lags behind. 
# So only run this after regular stats have been updated to make sure the Games Played count is up to date.
python update_stats.py --collect-play-types

python update_stats.py --collect-play-types --delay 1.0

# ONLY update team defensive play types (all 30 teams, skips player updates)
python update_stats.py --collect-team-play-types --delay 0.8

# ONLY update both zones (skips player updates)
python update_stats.py --collect-team-defense --collect-play-types --delay 1.0

# ONLY update both team defenses (zones + play types, skips player updates)
python update_stats.py --collect-team-defense --collect-team-play-types --delay 0.8

# Update EVERYTHING at once (recommended for daily updates)
python update_stats.py --collect-assist-zones --collect-team-defense --collect-team-play-types --collect-play-types --delay 1.0

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
python update_stats.py --collect-team-defense --delay 0.6  # Team defensive zones only (30 teams, quick)
python update_stats.py --collect-team-play-types --delay 0.8  # Team defensive play types only (30 teams, ~5-8 min)
python update_stats.py --collect-play-types --delay 1.0    # Player play types only (incremental, skips player updates)
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

5. **Team Defensive Play Types** (10 play types, same as above) - **NEW**
   - Tracks how teams defend against each play type
   - Shows **defensive efficiency** by play type (PPP allowed, FG% allowed)
   - Stores: PPP, FG%, eFG%, Points Per Game, Possessions Per Game, % of Opponent Possessions
   - Example: Bucks allow 0.807 PPP on PR ball handlers (elite) but 1.375 PPP on PR roll man (poor)
   - Used for matchup analysis

### Matchup Analysis - 
6. **Advanced Matchup Analysis** (`matchup_analysis.py`)
   - Analyzes today's NBA games for player vs. team defense matchups
   - **Three dimensions**: Shooting zones, Play types, Assist zones
   - **Enhanced features**:
     - League-average baselines for context
     - Team defensive rankings (1-30) for each zone/play type
     - Minimum sample size filters to avoid small-sample noise
     - Confidence intervals (Wilson score) to show reliability
   - **Usage**: `python matchup_analysis.py` or `python matchup_analysis.py --min-advantage 0.10`

**All stats are per-game averages** (except double-doubles, triple-doubles, and assist zones which are totals).

### Collect Team Defensive Play Types

**Command-line (Recommended):**
```bash
# Collect for all 30 teams
python update_stats.py --collect-team-play-types --delay 0.8

# Force re-collection even if data exists
python update_stats.py --collect-team-play-types --force-team-play-types --delay 0.8
```

**Python script:**
```python
from nba_stats_collector import NBAStatsCollector
from nba_api.stats.static import teams

collector = NBAStatsCollector()

# Single team
collector.collect_team_defensive_play_types("Milwaukee Bucks", delay=0.8)

# All teams (required for matchup analysis)
collector.collect_all_team_defensive_play_types(delay=0.8)

# Or manually:
all_teams = teams.get_teams()
for team in all_teams:
    print(f'Collecting {team["full_name"]}...')
    collector.collect_team_defensive_play_types(team['full_name'], delay=0.8)
```

### Run Matchup Analysis

```bash
# Analyze today's games
python matchup_analysis.py

# Custom date
python matchup_analysis.py --date 11/15/2025

# Filter by advantage threshold (only show 10%+ advantages)
python matchup_analysis.py --min-advantage 0.10
```

**What it shows:**
- Player shooting zones vs. opponent defensive zones
- Player play types vs. opponent defensive play types
- Player assist zones vs. opponent defensive zones
- League averages for context
- Team defensive rankings (1-30)
- Confidence intervals for reliability
- Minimum sample size filters

## Database

SQLite database with tables: `player_stats`, `player_shooting_zones`, `team_defensive_zones`, `player_assist_zones`, `player_play_types`, `team_defensive_play_types`

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

# View team defensive play types
df = pd.read_sql_query("""
    SELECT
        play_type,
        ppp,
        fg_pct,
        points_per_game,
        poss_per_game
    FROM team_defensive_play_types
    WHERE team_id = 1610612749  -- Milwaukee Bucks
      AND season = '2025-26'
    ORDER BY ppp ASC  -- Best (lowest PPP) to worst
""", conn)
print(df)
conn.close()

# Find worst defenses against a specific play type (exploitable)
df = pd.read_sql_query("""
    SELECT
        team_id,
        ppp,
        fg_pct,
        points_per_game
    FROM team_defensive_play_types
    WHERE play_type = 'Isolation'
      AND season = '2025-26'
    ORDER BY ppp DESC  -- Highest PPP = worst defense
    LIMIT 10
""", conn)
print(df)
conn.close()
```


## Dependencies

```bash
pip install nba_api
```
