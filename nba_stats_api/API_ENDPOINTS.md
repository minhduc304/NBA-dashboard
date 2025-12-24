# NBA Stats API - Endpoint Documentation

## Base URL
```
http://localhost:8080
```

## Available Endpoints

### Health Check
- **GET** `/health`
- Returns server health status

**Response:**
```json
{
  "status": "ok",
  "timestamp": 1764303014
}
```

---

## Player Endpoints

### 1. List All Players
- **GET** `/api/players`
- Returns all players (supports pagination)

**Query Parameters:**
- `limit` (optional): Number of players to return
- `offset` (optional): Number of players to skip

**Example:**
```bash
curl "http://localhost:8080/api/players?limit=10&offset=0"
```

### 2. Get Player by ID
- **GET** `/api/players/{id}`
- Returns single player's stats

**Example:**
```bash
curl "http://localhost:8080/api/players/1626164"
```

**Response:**
```json
{
  "player_id": 1626164,
  "player_name": "Devin Booker",
  "season": "2024-25",
  "points": 26.4,
  "assists": 6.9,
  "rebounds": 4.1,
  ...
}
```

### 3. Search Players by Name
- **GET** `/api/players/search?name={name}`
- Search for a player by full name

**Example:**
```bash
curl "http://localhost:8080/api/players/search?name=Devin%20Booker"
```

### 4. Get Player Shooting Zones
- **GET** `/api/players/{id}/shooting-zones`
- Returns shooting efficiency across court zones

**Example:**
```bash
curl "http://localhost:8080/api/players/1626164/shooting-zones"
```

**Response:**
```json
[
  {
    "player_id": 1626164,
    "season": "2024-25",
    "zone_name": "Restricted Area",
    "fgm": 38.0,
    "fga": 50.0,
    "fg_pct": 0.76,
    "efg_pct": 0.76
  },
  ...
]
```

### 5. Get Player Assist Zones
- **GET** `/api/players/{id}/assist-zones`
- Returns where player's assists lead to baskets

**Example:**
```bash
curl "http://localhost:8080/api/players/1626164/assist-zones"
```

### 6. Get Player Play Types
- **GET** `/api/players/{id}/play-types`
- Returns scoring breakdown by play type (Isolation, Transition, etc.)

**Example:**
```bash
curl "http://localhost:8080/api/players/1626164/play-types"
```

**Response:**
```json
[
  {
    "player_id": 1626164,
    "play_type": "PRBallHandler",
    "points_per_game": 7.7,
    "ppp": 0.923,
    "fg_pct": 0.463,
    "pct_of_total_points": 30.9
  },
  ...
]
```

### 7. Get Player Game Logs
- **GET** `/api/players/{id}/game-logs`
- Returns individual game stats for a player

**Query Parameters:**
- `limit` (optional): Number of games to return

**Example:**
```bash
curl "http://localhost:8080/api/players/1626164/game-logs?limit=10"
```

**Response:**
```json
[
  {
    "gameId": "0022400123",
    "playerId": "1626164",
    "teamId": 1610612756,
    "season": "2024-25",
    "gameDate": "2024-12-20",
    "matchup": "PHX vs LAL",
    "min": 36.5,
    "pts": 28,
    "reb": 5,
    "ast": 7,
    "stl": 1,
    "blk": 0,
    "fg3m": 3,
    "tov": 2
  },
  ...
]
```

### 8. Get Player Props
- **GET** `/api/players/{id}/props`
- Returns Underdog Fantasy prop lines for a player

**Example:**
```bash
curl "http://localhost:8080/api/players/1626164/props"
```

**Response:**
```json
{
  "playerName": "Devin Booker",
  "opponentId": 1610612747,
  "opponentName": "Los Angeles Lakers",
  "props": [
    {
      "statName": "points",
      "line": 26.5,
      "overOdds": -110,
      "underOdds": -110,
      "opponent": "Los Angeles Lakers",
      "scheduledAt": "2024-12-25T20:00:00Z"
    },
    ...
  ]
}
```

### 9. Get Player Play Type Matchup
- **GET** `/api/players/{id}/play-type-matchup?opponent_id={team_id}`
- Returns play type analysis vs specific opponent defense

**Query Parameters:**
- `opponent_id` (required): Team ID of the opponent

**Example:**
```bash
curl "http://localhost:8080/api/players/1626164/play-type-matchup?opponent_id=1610612747"
```

**Response:**
```json
{
  "playerName": "Devin Booker",
  "opponentName": "Los Angeles Lakers",
  "matchups": [
    {
      "playType": "PRBallHandler",
      "playerPpg": 7.7,
      "pctOfTotal": 30.9,
      "oppPpp": 0.95,
      "oppRank": 15
    },
    ...
  ]
}
```

---

## Team Endpoints

### 10. List All Teams
- **GET** `/api/teams`
- Returns all NBA teams

**Example:**
```bash
curl "http://localhost:8080/api/teams"
```

### 11. Get Team by ID
- **GET** `/api/teams/{id}`
- Returns single team info

**Example:**
```bash
curl "http://localhost:8080/api/teams/1610612756"
```

### 12. Search Teams
- **GET** `/api/teams/search?name={name}`
- Search for a team by name

**Example:**
```bash
curl "http://localhost:8080/api/teams/search?name=Suns"
```

### 13. Get Team Defensive Zones
- **GET** `/api/teams/{id}/defensive-zones`
- Returns opponent shooting efficiency by zone

**Example (Phoenix Suns):**
```bash
curl "http://localhost:8080/api/teams/1610612756/defensive-zones"
```

**Response:**
```json
[
  {
    "team_id": 1610612756,
    "zone_name": "Restricted Area",
    "opp_fgm": 238.0,
    "opp_fga": 342.0,
    "opp_fg_pct": 0.696,
    "opp_efg_pct": 0.696
  },
  ...
]
```

### 14. Get Team Defensive Play Types
- **GET** `/api/teams/{id}/defensive-play-types`
- Returns how team defends each play type

**Example:**
```bash
curl "http://localhost:8080/api/teams/1610612756/defensive-play-types"
```

---

## Schedule Endpoints

### 15. Get Schedule
- **GET** `/api/schedule`
- Returns games for a specific date or team

**Query Parameters:**
- `date` (optional): Date in YYYY-MM-DD format
- `team` (optional): Team abbreviation (e.g., "PHX", "LAL")

**Example:**
```bash
curl "http://localhost:8080/api/schedule?date=2024-12-25"
curl "http://localhost:8080/api/schedule?team=PHX"
```

**Response:**
```json
{
  "games": [
    {
      "gameId": "0022400123",
      "gameDate": "2024-12-25",
      "gameTime": "8:00 PM ET",
      "gameStatus": "Scheduled",
      "homeTeam": {
        "id": 1610612756,
        "name": "Suns",
        "abbreviation": "PHX",
        "city": "Phoenix"
      },
      "awayTeam": {
        "id": 1610612747,
        "name": "Lakers",
        "abbreviation": "LAL",
        "city": "Los Angeles"
      }
    }
  ],
  "count": 1
}
```

### 16. Get Today's Games
- **GET** `/api/schedule/today`
- Returns all games scheduled for today

**Example:**
```bash
curl "http://localhost:8080/api/schedule/today"
```

### 17. Get Upcoming Games
- **GET** `/api/schedule/upcoming`
- Returns upcoming scheduled games

**Example:**
```bash
curl "http://localhost:8080/api/schedule/upcoming"
```

### 18. Get Tomorrow's Rosters
- **GET** `/api/schedule/tomorrow/rosters`
- Returns tomorrow's games with full player rosters and injury status

**Example:**
```bash
curl "http://localhost:8080/api/schedule/tomorrow/rosters"
```

**Response:**
```json
{
  "games": [
    {
      "gameId": "0022400124",
      "gameDate": "2024-12-26",
      "gameTime": "7:00 PM ET",
      "gameStatus": "Scheduled",
      "homeTeam": {...},
      "awayTeam": {...},
      "homePlayers": [
        {
          "playerId": 1626164,
          "playerName": "Devin Booker",
          "position": "SG",
          "injuryStatus": "Available",
          "injuryDescription": null
        },
        ...
      ],
      "awayPlayers": [...]
    }
  ],
  "count": 1
}
```

---

## Common Team IDs

| Team | ID |
|------|-----|
| Atlanta Hawks | 1610612737 |
| Boston Celtics | 1610612738 |
| Brooklyn Nets | 1610612751 |
| Charlotte Hornets | 1610612766 |
| Chicago Bulls | 1610612741 |
| Cleveland Cavaliers | 1610612739 |
| Dallas Mavericks | 1610612742 |
| Denver Nuggets | 1610612743 |
| Detroit Pistons | 1610612765 |
| Golden State Warriors | 1610612744 |
| Houston Rockets | 1610612745 |
| Indiana Pacers | 1610612754 |
| LA Clippers | 1610612746 |
| Los Angeles Lakers | 1610612747 |
| Memphis Grizzlies | 1610612763 |
| Miami Heat | 1610612748 |
| Milwaukee Bucks | 1610612749 |
| Minnesota Timberwolves | 1610612750 |
| New Orleans Pelicans | 1610612740 |
| New York Knicks | 1610612752 |
| Oklahoma City Thunder | 1610612760 |
| Orlando Magic | 1610612753 |
| Philadelphia 76ers | 1610612755 |
| Phoenix Suns | 1610612756 |
| Portland Trail Blazers | 1610612757 |
| Sacramento Kings | 1610612758 |
| San Antonio Spurs | 1610612759 |
| Toronto Raptors | 1610612761 |
| Utah Jazz | 1610612762 |
| Washington Wizards | 1610612764 |

---

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200 OK**: Successful request
- **404 NOT FOUND**: Resource not found
- **500 INTERNAL SERVER ERROR**: Server error

**Error Response Format:**
```json
{
  "error": "404 Not Found",
  "message": "Resource not found"
}
```

---

## CORS

CORS is enabled for all origins (configured for NextJS development).

---

## Running the Server

```bash
# Set up environment
cp .env.example .env
# Edit .env with your database path

# Run the server
cargo run

# Server will start on http://localhost:8080
```
