# NBA Analytics Platform

A comprehensive NBA analytics platform for player prop analysis. Combines automated data collection, machine learning predictions, and an interactive visualization dashboard.

## Overview

This project consists of three main components:

### 1. Data Collection Pipeline (Python)

Automated collection of NBA statistics from multiple sources:

- **NBA API**: Player stats, game logs, shooting zones, assist zones, play types, team defensive metrics
- **Underdog Fantasy**: Player prop lines with American odds
- **PrizePicks**: Alternative prop lines
- **The Odds API**: Props from DraftKings, FanDuel, Bovada, and others

Data is stored in SQLite and processed into ML-ready features including rolling averages (L5, L10, L20), home/away splits, rest days, and matchup context.

### 2. ML Prediction System (Python)

XGBoost/LightGBM-based models that predict player prop outcomes:

- **Stat Types**: Points, rebounds, assists (extensible to other stats)
- **Features**: ~60+ features including rolling stats, matchup data, odds/vig, injury context
- **Training**: Time-based train/validation/test split with probability calibration
- **Paper Trading**: Simulated betting to track prediction accuracy
- **Output**: Hit probability, predicted value, confidence scores

### 3. Interactive Dashboard (Next.js + Rust API)

- **Player Search**: Browse players with upcoming games
- **Stat Charts**: Interactive game log visualization with adjustable prop lines
- **Hit Rate Calculator**: Real-time hit rate as you move the line
- **Shooting Zones**: Player shot distribution vs opponent defensive zones
- **Assist Zones**: Where a player's assists lead to made baskets
- **Play Type Matchups**: Scoring breakdown vs opponent defensive rankings
- **Prop Lines**: Current lines with over/under odds

## Project Structure

```
nba_stats_dashboard/
├── src/                        # Python backend
│   ├── cli/                    # CLI commands (Click framework)
│   │   ├── main.py             # Entry point
│   │   ├── player.py           # Player commands
│   │   ├── team.py             # Team commands
│   │   ├── ml.py               # ML pipeline commands
│   │   └── scrape.py           # Scraping commands
│   ├── collectors/             # NBA API data collectors
│   │   ├── player.py           # Player stats collector
│   │   ├── team.py             # Team data collector
│   │   ├── zones.py            # Shooting/assist zones
│   │   ├── play_types.py       # Play type data
│   │   └── injuries.py         # Injury reports
│   ├── scrapers/               # Prop line scrapers
│   │   ├── underdog.py         # Underdog Fantasy
│   │   ├── prizepicks.py       # PrizePicks
│   │   └── odds_api.py         # The Odds API
│   ├── ml_pipeline/            # Machine learning system
│   │   ├── trainer.py          # Model training
│   │   ├── predictor.py        # Inference
│   │   ├── features.py         # Feature engineering
│   │   ├── paper_trading.py    # Simulated trading
│   │   └── outcome_tracker.py  # Label actual results
│   ├── db/                     # Database layer
│   └── models/                 # Data models
├── backend/                    # Rust REST API (Axum)
│   └── src/
│       ├── main.rs             # Server setup
│       └── routes/             # API endpoints
├── frontend/                   # Next.js dashboard
│   ├── app/                    # Pages
│   ├── components/             # React components
│   ├── hooks/                  # Custom hooks
│   └── lib/                    # Utilities
├── data/                       # SQLite database
├── trained_models/             # Model artifacts (.joblib)
├── logs/                       # Application logs
├── tests/                      # Test suite
├── scripts/                    # Automation scripts
└── nba                         # CLI executable
```

## CLI Commands

The project uses a unified CLI interface via `./nba`:

```bash
./nba --help                    # Show all available commands
```

### Player Commands
```bash
./nba player update <name>      # Update single player stats
./nba player game-logs          # Collect game logs
./nba player zones              # Collect shooting/assist zones
./nba player play-types         # Collect play type data
```

### Team Commands
```bash
./nba team defense              # Collect defensive zone data
./nba team play-types           # Collect defensive play type data
./nba team pace                 # Collect pace metrics
```

### Collection Commands
```bash
./nba collect all               # Full data collection
./nba collect injuries          # Just injuries
./nba collect game-scores       # Schedule scores
```

### ML Pipeline Commands
```bash
./nba ml pipeline               # Run daily ML pipeline
./nba ml pipeline --dry-run     # Show steps without executing
./nba ml train                  # Train models for all priority stats
./nba ml train --stat points    # Train specific stat model
./nba ml validate               # Validate model accuracy
./nba ml tune                   # Hyperparameter tuning (Optuna)
./nba ml paper status           # Paper trading status
./nba ml paper report           # Paper trading performance report
```

### Scraping Commands
```bash
./nba scrape all                # Scrape props from all sources
./nba scrape underdog           # Underdog Fantasy props
./nba scrape odds-api           # The Odds API props
./nba scrape prizepicks         # PrizePicks props
```

### Global Options
```bash
--db <path>                     # Specify database path
--delay <seconds>               # API delay between requests
--rostered-only                 # Skip free agents
-v, --verbose                   # Verbose logging
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Rust (for backend API)

### Installation

```bash
# Clone repository
git clone <repo-url>
cd nba_stats_dashboard

# Install Python dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Build Rust backend
cd backend && cargo build --release && cd ..
```

### Initial Data Collection

```bash
# 1. Collect historical game logs for ML training
./nba collect all --collect-historical 2024-25 2023-24

# 2. Collect team defensive data
./nba team defense --delay 0.8
./nba team play-types

# 3. Collect player play types
./nba player play-types --delay 1.0

# 4. Compute rolling statistics
./nba ml pipeline --step rolling
```

### Daily Operations

```bash
# Run the daily pipeline (game logs, injuries, features, props, predictions)
./nba ml pipeline

# Or run individual steps
./nba ml pipeline --step logs      # Just game logs
./nba ml pipeline --step props     # Just prop outcomes
```

### Start the Dashboard

```bash
# Terminal 1: Start Rust API (port 8080)
cd backend && cargo run --release

# Terminal 2: Start Next.js frontend (port 3000)
cd frontend && npm run dev
```

Visit `http://localhost:3000` to access the dashboard.

## Automation

The system runs automatically via launchd/cron:

| Schedule | Task | Description |
|----------|------|-------------|
| 9 AM daily | `./nba ml pipeline` | Game logs, injuries, features, prop outcomes, predictions |
| 10 AM, 2 PM, 6 PM, 10 PM | `./nba scrape all` | Props from Underdog + PrizePicks |

## Model Training

```bash
# Train all priority stat models (points, rebounds, assists)
./nba ml train

# Train specific stat
./nba ml train --stat points

# Hyperparameter tuning
./nba ml tune --stat points --trials 100

# Validate model performance
./nba ml validate --summary
```

## Paper Trading

Track prediction accuracy without real money:

```bash
# Check pending predictions
./nba ml paper status

# Update with actual results
./nba ml paper update

# View performance report
./nba ml paper report
```

## Database Schema

Key tables:
- `player_stats` - Season averages
- `player_game_logs` - Individual game stats with derived features
- `player_rolling_stats` - L5/L10/L20 rolling averages
- `player_shooting_zones` / `player_assist_zones` - Zone-based analysis
- `player_play_types` / `team_defensive_play_types` - Play type breakdowns
- `underdog_props` / `odds_api_props` / `prizepicks_props` - Prop lines
- `all_props` - Unified props from all sources
- `prop_outcomes` - Labeled training data with actual results
- `paper_trades` - Paper trading predictions and results

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Data Collection** | Python, NBA API, Web Scraping |
| **ML Pipeline** | XGBoost, LightGBM, scikit-learn, Optuna |
| **Database** | SQLite |
| **Backend API** | Rust, Axum, SQLx |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS |
| **UI Components** | Radix UI, Recharts, Lucide Icons |
| **CLI** | Click (Python) |

## Environment Variables

Create a `.env` file:

```bash
# Underdog credentials (for scraping)
UNDERDOG_EMAIL=your_email
UNDERDOG_PASSWORD=your_password

# The Odds API key
ODDS_API_KEY=your_api_key

# Database path (optional, defaults to data/nba_stats.db)
DATABASE_URL=sqlite:///data/nba_stats.db
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_collectors/test_player.py -v
```

## Logs

Logs are stored in `logs/`:
- `daily_pipeline.log` - Daily ML pipeline execution
- `scrape_props.log` - Props scraping
- `paper_trading.log` - Paper trading operations
- `launchd.log` - Scheduled job output

## License

MIT