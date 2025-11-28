use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;

#[derive(Debug)]
pub enum ApiError {
    NotFound,
    DatabaseError(sqlx::Error),
    InternalError,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
    message: String,
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, error_message) = match self {
            ApiError::NotFound => (
                StatusCode::NOT_FOUND,
                "Resource not found".to_string(),
            ),
            ApiError::DatabaseError(err) => (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Database error: {}", err),
            ),
            ApiError::InternalError => (
                StatusCode::INTERNAL_SERVER_ERROR,
                "Internal server error".to_string(),
            ),
        };

        let body = Json(ErrorResponse {
            error: status.to_string(),
            message: error_message,
        });

        (status, body).into_response()
    }
}

impl From<sqlx::Error> for ApiError {
    fn from(err: sqlx::Error) -> Self {
        ApiError::DatabaseError(err)
    }
}
