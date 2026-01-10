use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
};
use sqlx::sqlite::SqlitePool;
use crate::models::{TeamDefensiveZones};
use crate::db;

// GET /api/teams/:id/defensive-zones - Get team's defensive zones
pub async fn get_team_defensive_zones(
    State(pool): State<SqlitePool>,
    Path(team_id): Path<i64>,
) -> Result<Json<Vec<TeamDefensiveZones>>, StatusCode> {
    let zones = db::get_defensive_zones(&pool, team_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if zones.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(Json(zones))
}
