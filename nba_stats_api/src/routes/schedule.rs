use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::Json,
};
use serde::Deserialize;
use sqlx::sqlite::SqlitePool;
use std::process::Command;
use crate::db;
use crate::models::{ScheduleResponse, ScheduleGame, RosterResponse, GameWithRosters, TeamInfo};

/// Query parameters for filtering schedule
#[derive(Deserialize)]
pub struct ScheduleQuery {
    /// Filter by date (format: YYYY-MM-DD)
    #[serde(default)]
    pub date: Option<String>,
    /// Filter by team abbreviation (e.g., "LAL", "BOS")
    #[serde(default)]
    pub team: Option<String>,
}

/// GET /api/schedule - Get NBA game schedule
///
/// Query params:
/// - date: Filter games by date (YYYY-MM-DD format)
/// - team: Filter games by team abbreviation
///
/// First tries to read from SQLite cache. Falls back to Python script if no cached data.
pub async fn get_schedule(
    State(pool): State<SqlitePool>,
    Query(params): Query<ScheduleQuery>,
) -> Result<Json<ScheduleResponse>, StatusCode> {
    // Try to get data from SQLite first
    let db_result = if let Some(date) = &params.date {
        db::get_schedule_by_date(&pool, date).await
    } else if let Some(team) = &params.team {
        db::get_schedule_by_team(&pool, team).await
    } else {
        db::get_todays_schedule(&pool).await
    };

    // If we got data from the database, return it
    if let Ok(rows) = db_result {
        if !rows.is_empty() {
            let games: Vec<ScheduleGame> = rows.iter().map(|r| r.to_schedule_game()).collect();
            let count = games.len();
            return Ok(Json(ScheduleResponse { games, count }));
        }
    }

    // Fallback to Python script if no cached data
    tracing::info!("No cached schedule data, falling back to Python script");
    get_schedule_from_python(params).await
}

/// GET /api/schedule/today - Get today's games
///
/// First tries to read from SQLite cache. Falls back to Python script if no cached data.
pub async fn get_todays_games(
    State(pool): State<SqlitePool>,
) -> Result<Json<ScheduleResponse>, StatusCode> {
    // Try to get data from SQLite first
    if let Ok(rows) = db::get_todays_schedule(&pool).await {
        if !rows.is_empty() {
            let games: Vec<ScheduleGame> = rows.iter().map(|r| r.to_schedule_game()).collect();
            let count = games.len();
            return Ok(Json(ScheduleResponse { games, count }));
        }
    }

    // Fallback to Python script
    tracing::info!("No cached today's schedule, falling back to Python script");
    get_schedule_from_python(ScheduleQuery { date: None, team: None }).await
}

/// GET /api/schedule/upcoming - Get upcoming games for next 7 days
///
/// First tries to read from SQLite cache. Falls back to Python script if no cached data.
pub async fn get_upcoming_games(
    State(pool): State<SqlitePool>,
) -> Result<Json<ScheduleResponse>, StatusCode> {
    // Try to get data from SQLite first
    if let Ok(rows) = db::get_upcoming_schedule(&pool, 7).await {
        if !rows.is_empty() {
            let games: Vec<ScheduleGame> = rows.iter().map(|r| r.to_schedule_game()).collect();
            let count = games.len();
            return Ok(Json(ScheduleResponse { games, count }));
        }
    }

    // Fallback to Python script
    tracing::info!("No cached upcoming schedule, falling back to Python script");
    let output = Command::new("../venv/bin/python")
        .arg("../nba_schedule.py")
        .arg("--upcoming")
        .arg("7")
        .output()
        .map_err(|e| {
            tracing::error!("Failed to execute Python script: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        tracing::error!("Python script failed: {}", stderr);
        return Err(StatusCode::INTERNAL_SERVER_ERROR);
    }

    let stdout = String::from_utf8_lossy(&output.stdout);

    let response: ScheduleResponse = serde_json::from_str(&stdout)
        .map_err(|e| {
            tracing::error!("Failed to parse schedule response: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(response))
}

/// Fallback: Get schedule from Python script (used when no cached data available)
async fn get_schedule_from_python(params: ScheduleQuery) -> Result<Json<ScheduleResponse>, StatusCode> {
    let mut args = vec![];

    if let Some(date) = &params.date {
        args.push("--date".to_string());
        args.push(date.clone());
    } else if params.team.is_none() {
        args.push("--today".to_string());
    }

    if let Some(team) = &params.team {
        args.push("--team".to_string());
        args.push(team.clone());
    }

    let output = Command::new("../venv/bin/python")
        .arg("../nba_schedule.py")
        .args(&args)
        .output()
        .map_err(|e| {
            tracing::error!("Failed to execute Python script: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        tracing::error!("Python script failed: {}", stderr);
        return Err(StatusCode::INTERNAL_SERVER_ERROR);
    }

    let stdout = String::from_utf8_lossy(&output.stdout);

    let response: ScheduleResponse = serde_json::from_str(&stdout)
        .map_err(|e| {
            tracing::error!("Failed to parse schedule response: {}", e);
            tracing::error!("Raw output: {}", stdout);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(response))
}

/// GET /api/schedule/tomorrow/rosters - Get tomorrow's games with full player rosters
///
/// Returns games for the next game day (tomorrow, or the next day with games if tomorrow is empty).
/// Each game includes full roster for both teams with player info and injury status.
pub async fn get_tomorrow_rosters(
    State(pool): State<SqlitePool>,
) -> Result<Json<RosterResponse>, StatusCode> {
    // Get tomorrow's games (or next game day)
    let schedule_rows = db::get_next_game_day_schedule(&pool)
        .await
        .map_err(|e| {
            tracing::error!("Failed to get next game day schedule: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    if schedule_rows.is_empty() {
        return Ok(Json(RosterResponse {
            games: vec![],
            count: 0,
        }));
    }

    // Group games by the first game's date (they should all be the same day)
    let target_date = &schedule_rows[0].game_date;
    let games_for_day: Vec<_> = schedule_rows
        .iter()
        .filter(|g| &g.game_date == target_date)
        .collect();

    let mut games_with_rosters = Vec::new();

    for game in games_for_day {
        // Get rosters for both teams
        let home_roster = db::get_team_roster(&pool, game.home_team_id)
            .await
            .map_err(|e| {
                tracing::error!("Failed to get home roster for team {}: {}", game.home_team_id, e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

        let away_roster = db::get_team_roster(&pool, game.away_team_id)
            .await
            .map_err(|e| {
                tracing::error!("Failed to get away roster for team {}: {}", game.away_team_id, e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

        games_with_rosters.push(GameWithRosters {
            game_id: game.game_id.clone(),
            game_date: game.game_date.clone(),
            game_time: game.game_time.clone().unwrap_or_else(|| "TBD".to_string()),
            game_status: game.game_status.clone().unwrap_or_default(),
            home_team: TeamInfo {
                id: game.home_team_id,
                name: game.home_team_name.clone().unwrap_or_default(),
                abbreviation: game.home_team_abbreviation.clone().unwrap_or_default(),
                city: game.home_team_city.clone().unwrap_or_default(),
            },
            away_team: TeamInfo {
                id: game.away_team_id,
                name: game.away_team_name.clone().unwrap_or_default(),
                abbreviation: game.away_team_abbreviation.clone().unwrap_or_default(),
                city: game.away_team_city.clone().unwrap_or_default(),
            },
            home_players: home_roster.iter().map(|r| r.to_roster_player()).collect(),
            away_players: away_roster.iter().map(|r| r.to_roster_player()).collect(),
        });
    }

    let count = games_with_rosters.len();
    Ok(Json(RosterResponse {
        games: games_with_rosters,
        count,
    }))
}
