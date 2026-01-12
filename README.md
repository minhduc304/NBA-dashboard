# NBA Stats Dashboard

A comprehensive NBA analytics platform for player prop analysis. Combines automated data collection, machine learning predictions, and an interactive visualization dashboard.

## Overview

This project consists of three main components:

### 1. Data Collection Pipeline

Automated collection of NBA statistics from multiple sources:

- **NBA API**: Player stats, game logs, shooting zones, assist zones, play types, team defensive metrics
- **Underdog Fantasy**: Player prop lines with American odds (scraped 3x daily)
- **Odds API**: Props from DraftKings, FanDuel, and BetOnline (scraped daily)

Data is stored in SQLite and processed into ML-ready features including rolling averages (L5, L10, L20), home/away splits, rest days, and matchup context.

### 2. ML Prediction System

XGBoost-based models that predict player prop outcomes:

- **Stat Types**: Points, rebounds, assists (extensible to other stats)
- **Features**: ~60+ features including rolling stats, matchup data, odds/vig, injury context
- **Training**: Time-based train/validation/test split to prevent data leakage
- **Output**: Hit probability, edge calculation, confidence scores

See [`docs/ml_system.md`](docs/ml_system.md) for detailed documentation.

### 3. Interactive Dashboard

Next.js frontend for player analysis:

- **Player Search**: Browse players with upcoming games
- **Stat Charts**: Interactive game log visualization with adjustable prop lines
- **Hit Rate Calculator**: Real-time hit rate as you move the line
- **Shooting Zones**: Player shot distribution vs opponent defensive zones (basketball court visualization)
- **Assist Zones**: Where a player's assists lead to made baskets vs opponent defense
- **Play Type Matchups**: Scoring breakdown (isolation, P&R, spot-up, etc.) vs opponent defensive rankings
- **Prop Lines**: Current Underdog lines with over/under odds

## Project Structure

```
nba_stats_dashboard/
├── src/                    # Python backend
│   ├── nba_stats_collector.py  # NBA API data collection
│   ├── underdog/           # Underdog scraper
│   ├── odds/               # Odds API integration
│   ├── ml/                 # Machine learning models
│   └── prop_outcome_tracker.py  # Label props with actual results
├── scripts/                # Automation scripts
│   ├── daily_ml_update.py  # Daily pipeline (6 AM via cron)
│   ├── scrape_props.py     # Props scraping (scheduled via launchd)
│   ├── train_models.py     # Model training
│   └── predict_props.py    # Generate predictions
├── frontend/               # Next.js dashboard
│   ├── app/                # Pages
│   └── components/         # React components
├── data/                   # SQLite database
├── models/                 # Trained model artifacts
└── docs/                   # Documentation
```

## Data Collection Options

The `scripts/update_stats.py` script supports various data collection modes:

### Core Stats
| Flag | Description | API Calls |
|------|-------------|-----------|
| (none) | Update existing players with new games | ~1 per player with new games |
| `--collect-game-logs` | All player game logs (incremental) | 1 |
| `--collect-game-scores` | Final scores for schedule table | 1 |
| `--collect-injuries` | Current injury report (NBA.com + ESPN fallback) | 1-2 |

### Zone & Play Type Analysis
| Flag | Description | API Calls |
|------|-------------|-----------|
| `--collect-team-defense` | Team defensive zones (all 30 teams) | 30 |
| `--collect-team-play-types` | Team defensive play types (Synergy) | 30 |
| `--collect-assist-zones` | Player assist zones (incremental) | ~1 per player |
| `--collect-play-types` | Player play types (incremental) | ~1 per player |

### Historical & ML Features
| Flag | Description | API Calls |
|------|-------------|-----------|
| `--collect-historical 2024-25 2023-24` | Historical game logs for specified seasons | 1 per season |
| `--collect-pace` | Team pace data | 1 |
| `--compute-rolling-stats` | L5/L10/L20 rolling averages | 0 (local computation) |

### Modifiers
| Flag | Description |
|------|-------------|
| `--delay 2.0` | Seconds between API calls (increase if rate limited) |
| `--rostered-only` | Skip free agents (~45 fewer API calls) |
| `--include-new` | Add new players not yet in database |
| `--force-play-types` | Re-collect even if data exists |

## Ideal Data Collection Workflow

### Initial Setup (One-Time)

```bash
# 1. Collect historical game logs for ML training (3 seasons recommended)
python scripts/update_stats.py --collect-historical 2024-25 2023-24 2022-23

# 2. Collect all current player stats
python scripts/update_stats.py --include-new --rostered-only --delay 1.0

# 3. Collect team data (defensive zones + play types)
python scripts/update_stats.py --collect-team-defense --collect-team-play-types --delay 0.8

# 4. Collect player play types (can take a while)
python scripts/update_stats.py --collect-play-types --delay 1.0

# 5. Compute rolling statistics for ML
python scripts/update_stats.py --compute-rolling-stats
```

### Daily Updates

```bash
# Quick daily update (game logs + injuries + game scores)
python scripts/update_stats.py --collect-game-logs --collect-injuries --collect-game-scores

# Or run the full automated pipeline
python scripts/daily_ml_update.py
```

### Weekly Updates

```bash
# Team pace data (changes slowly)
python scripts/update_stats.py --collect-pace

# Team defensive play types (refresh rankings)
python scripts/update_stats.py --collect-team-play-types --delay 0.8
```

## Quick Start

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run initial data collection (see workflow above)
python scripts/update_stats.py --collect-game-logs

# Train models (after collecting sufficient data)
python scripts/train_models.py --stat points

# Generate predictions
python scripts/predict_props.py

# Start dashboard
cd frontend && npm install && npm run dev
cd api && cargo run --release
```

## Automation

The system runs automatically:

| Schedule | Task | Description |
|----------|------|-------------|
| 6 AM daily | `daily_ml_update.py` | Game logs, injuries, features, prop outcomes, Odds API |
| 10 AM, 2 PM, 6 PM | `scrape_props.py` | Underdog props collection |

## Database Schema

Key tables:
- `player_stats` - Season averages
- `player_game_logs` - Individual game stats
- `player_shooting_zones` / `player_assist_zones` - Zone-based analysis
- `player_play_types` / `team_defensive_play_types` - Play type breakdowns
- `underdog_props` / `odds_api_props` - Prop lines from sportsbooks
- `prop_outcomes` - Labeled training data with actual results

## Tech Stack

- **Backend**: Python, SQLite, XGBoost
- **Frontend**: Next.js, React, TypeScript, Tailwind CSS
- **Data Sources**: NBA API, Underdog Fantasy, The Odds API
