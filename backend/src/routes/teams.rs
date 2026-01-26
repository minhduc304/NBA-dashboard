use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::Json,
};
use serde::Deserialize;
use sqlx::sqlite::SqlitePool;
use crate::models::{Team, TeamStats};
use crate::db;

// Query parameters for searching teams
#[derive(Deserialize)]
pub struct SearchTeamQuery {
    #[serde(default)]
    abbr: Option<String>,
}

// GET /api/teams - List all teams
pub async fn get_teams(
    State(pool): State<SqlitePool>,
) -> Result<Json<Vec<Team>>, StatusCode> {
    let teams = db::get_all_teams(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(teams))
}

// GET /api/teams/:id - Get team by ID
pub async fn get_team_by_id(
    State(pool): State<SqlitePool>,
    Path(team_id): Path<i64>,
) -> Result<Json<Team>, StatusCode> {
    let team = db::get_team_by_id(&pool, team_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(team))
}

// GET /api/teams/search?abbr=LAL - Search team by abbreviation
pub async fn search_team(
    State(pool): State<SqlitePool>,
    Query(params): Query<SearchTeamQuery>,
) -> Result<Json<Team>, StatusCode> {
    let abbr = params.abbr.ok_or(StatusCode::BAD_REQUEST)?;

    let team = db::get_team_by_abbreviation(&pool, &abbr)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(team))
}

// GET /api/teams/:id/stats - Get team pace and ratings
pub async fn get_team_stats(
    State(pool): State<SqlitePool>,
    Path(team_id): Path<i64>,
) -> Result<Json<TeamStats>, StatusCode> {
    let stats = db::get_team_stats(&pool, team_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(stats))
}
