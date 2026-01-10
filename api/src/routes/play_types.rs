use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
};
use sqlx::sqlite::SqlitePool;
use crate::models::TeamDefensivePlayTypes;
use crate::db;

// GET /api/teams/:id/defensive-play-types - Get team's defensive play types
pub async fn get_team_defensive_play_types(
    State(pool): State<SqlitePool>,
    Path(team_id): Path<i64>,
) -> Result<Json<Vec<TeamDefensivePlayTypes>>, StatusCode> {
    let play_types = db::get_defensive_play_types(&pool, team_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if play_types.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(Json(play_types))
}
