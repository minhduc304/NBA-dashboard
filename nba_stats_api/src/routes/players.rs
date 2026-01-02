use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::Json,
};
use serde::Deserialize;
use sqlx::sqlite::SqlitePool;
use crate::models::{PlayerStats, PlayTypeMatchup, PlayTypeMatchupResponse};
use crate::db;

// Query parameters for listing players
#[derive(Deserialize)]
pub struct ListPlayersQuery {
    #[serde(default)]
    limit: Option<i64>,
    #[serde(default)]
    offset: Option<i64>,
}

// Query parameters for searching players
#[derive(Deserialize)]
pub struct SearchQuery {
    name: String,
}

// GET /api/players - List all players
pub async fn get_players(
    State(pool): State<SqlitePool>,
    Query(params): Query<ListPlayersQuery>,
) -> Result<Json<Vec<PlayerStats>>, StatusCode> {
    // Get all players from database
    let players = db::get_all_players(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Apply pagination if provided
    let start = params.offset.unwrap_or(0) as usize;
    let end = params.limit.map(|l| start + l as usize).unwrap_or(players.len());

    let paginated = players.into_iter().skip(start).take(end - start).collect();

    Ok(Json(paginated))
}

// GET /api/players/:id - Get player by ID
pub async fn get_player_by_id(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<PlayerStats>, StatusCode> {
    let player = db::get_player_by_id(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(player))
}

// GET /api/players/search?name=LeBron - Search players by name
pub async fn search_players(
    State(pool): State<SqlitePool>,
    Query(params): Query<SearchQuery>,
) -> Result<Json<PlayerStats>, StatusCode> {
    let player = db::search_players(&pool, &params.name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(player))
}

// GET /api/players/:id/shooting-zones - Get player's shooting zones
pub async fn get_player_shooting_zones(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<Vec<crate::models::PlayerShootingZones>>, StatusCode> {
    let zones = db::get_shooting_zones(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if zones.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(Json(zones))
}

// GET /api/players/:id/assist-zones - Get player's assist zones
pub async fn get_player_assist_zones(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<Vec<crate::models::PlayerAssistZones>>, StatusCode> {
    let zones = db::get_assist_zones(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if zones.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(Json(zones))
}

// GET /api/players/:id/play-types - Get player's play types breakdown
pub async fn get_player_play_types(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<Vec<crate::models::PlayerPlayTypes>>, StatusCode> {
    let play_types = db::get_player_playtypes(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if play_types.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(Json(play_types))
}

// Query parameters for game logs
#[derive(Deserialize)]
pub struct GameLogsQuery {
    /// Number of games to return (default: 20, max: 82)
    /// Matches the "games" slider in the frontend UI
    #[serde(default = "default_limit")]
    limit: i64,
}

fn default_limit() -> i64 {
    20
}

// GET /api/players/:id/game-logs - Get player's game-by-game stats
pub async fn get_player_game_logs(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
    Query(params): Query<GameLogsQuery>,
) -> Result<Json<Vec<crate::models::PlayerGameLog>>, StatusCode> {
    // Cap limit at 82 (max games in a season)
    let limit = params.limit.min(82);

    let game_logs = db::get_player_game_logs(&pool, player_id, limit)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(game_logs))
}

// Query parameters for play type matchup
#[derive(Deserialize)]
pub struct PlayTypeMatchupQuery {
    opponent_id: i64,
}

// GET /api/players/:id/play-type-matchup?opponent_id=123 - Get player's play type matchup vs opponent
pub async fn get_player_play_type_matchup(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
    Query(params): Query<PlayTypeMatchupQuery>,
) -> Result<Json<PlayTypeMatchupResponse>, StatusCode> {
    // Get player info
    let player = db::get_player_by_id(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    // Get opponent team info
    let opponent = db::get_team_by_id(&pool, params.opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    // Get player play types
    let player_play_types = db::get_player_playtypes(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Get opponent defensive play types
    let opp_defense = db::get_defensive_play_types(&pool, params.opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Get all team defensive rankings
    let ranks = db::get_team_defensive_play_type_ranks(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Build matchup data
    let mut matchups: Vec<PlayTypeMatchup> = player_play_types
        .iter()
        .filter_map(|pt| {
            // Find opponent's defensive stats for this play type
            let opp_def = opp_defense.iter().find(|d| d.play_type == pt.play_type)?;
            let rank = ranks.get(&(params.opponent_id, pt.play_type.clone())).copied().unwrap_or(0);

            Some(PlayTypeMatchup {
                play_type: pt.play_type.clone(),
                player_ppg: pt.points_per_game,
                pct_of_total: pt.pct_of_total_points,
                opp_ppp: opp_def.ppp,
                opp_rank: rank,
            })
        })
        .collect();

    // Sort by player PPG descending
    matchups.sort_by(|a, b| b.player_ppg.partial_cmp(&a.player_ppg).unwrap_or(std::cmp::Ordering::Equal));

    Ok(Json(PlayTypeMatchupResponse {
        player_name: player.player_name,
        opponent_name: opponent.full_name,
        matchups,
    }))
}

// Query parameters for assist zone matchup
#[derive(Deserialize)]
pub struct AssistZoneMatchupQuery {
    opponent_id: i64,
}

// GET /api/players/:id/assist-zone-matchup?opponent_id=123 - Get player's assist zone matchup vs opponent
pub async fn get_player_assist_zone_matchup(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
    Query(params): Query<AssistZoneMatchupQuery>,
) -> Result<Json<crate::models::AssistZoneMatchupResponse>, StatusCode> {
    let matchup = db::get_assist_zones_with_team_defense(&pool, player_id, params.opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(matchup))
}
