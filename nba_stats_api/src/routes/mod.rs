// TODO: Your API route handlers go here
//
// Learning objectives:
// 1. Understand Axum handlers and extractors
// 2. Learn how to use Path, Query, State extractors
// 3. Practice returning Json responses
// 4. Learn error handling in handlers
//
// Suggested structure:
// pub mod health;      // Health check endpoint
// pub mod players;     // Player-related endpoints
// pub mod zones;       // Shooting/assist/defense zones
// pub mod play_types;  // Play type endpoints
//
// Each submodule should export functions that are Axum handlers:
// pub async fn get_players(State(pool): State<SqlitePool>) -> Result<Json<Vec<Player>>, ApiError>
//
// Tips:
// - Start simple with a health check
// - Build up complexity gradually
// - Test each endpoint as you build it
