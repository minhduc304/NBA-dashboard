use axum::{response::Json, http::StatusCode};
use serde::Serialize;

#[derive(Serialize)]
pub struct HealthResponse {
    status: String,
    timestamp: i64,
}

pub async fn health_check() -> (StatusCode, Json<HealthResponse>) {
    let response = HealthResponse {
        status: "ok".to_string(),
        timestamp: chrono::Utc::now().timestamp(),
    };

    (StatusCode::OK, Json(response))
}