# NBA Stats API - Endpoint Documentation

## Base URL
```
http://localhost:3000
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
curl "http://localhost:3000/api/players?limit=10&offset=0"
```

### 2. Get Player by ID
- **GET** `/api/players/{id}`
- Returns single player's stats

**Example:**
```bash
curl "http://localhost:3000/api/players/1626164"
```

**Response:**
```json
{
  "player_id": 1626164,
  "player_name": "Devin Booker",
  "season": "2025-26",
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
curl "http://localhost:3000/api/players/search?name=Devin%20Booker"
```

### 4. Get Player Shooting Zones
- **GET** `/api/players/{id}/shooting-zones`
- Returns shooting efficiency across 6 court zones

**Example:**
```bash
curl "http://localhost:3000/api/players/1626164/shooting-zones"
```

**Response:**
```json
[
  {
    "player_id": 1626164,
    "season": "2025-26",
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
curl "http://localhost:3000/api/players/1626164/assist-zones"
```

### 6. Get Player Play Types
- **GET** `/api/players/{id}/play-types`
- Returns scoring breakdown by play type (Isolation, Transition, etc.)

**Example:**
```bash
curl "http://localhost:3000/api/players/1626164/play-types"
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

---

## Team Defense Endpoints

### 7. Get Team Defensive Zones
- **GET** `/api/teams/{id}/defensive-zones`
- Returns opponent shooting efficiency by zone

**Example (Phoenix Suns - 1610612756):**
```bash
curl "http://localhost:3000/api/teams/1610612756/defensive-zones"
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

### 8. Get Team Defensive Play Types
- **GET** `/api/teams/{id}/defensive-play-types`
- Returns how team defends each play type

**Example:**
```bash
curl "http://localhost:3000/api/teams/1610612756/defensive-play-types"
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

# Server will start on http://localhost:3000
```

---

## Next Steps

- Add authentication/API keys
- Implement rate limiting
- Add caching layer
- Deploy to production
- Create OpenAPI/Swagger documentation
