use sqlx::sqlite::SqlitePool;
use axum::{routing::get, Router};
use std::net::{Ipv4Addr, SocketAddr};
use tower_http::cors::{CorsLayer, Any};
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod routes;
mod models;
mod db;
mod error;

#[tokio::main]
async fn main() {
    // Initialize tracing/logging
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    tracing::info!("Starting api server...");
    
    dotenvy::dotenv().ok();
    
    // Create database connection pool
    let db_url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must be set in .env");
    
    let pool = SqlitePool::connect(&db_url)
        .await
        .expect("Failed to connect to database");
    
    tracing::info!("Database connection established.");
    
    let host: Ipv4Addr = std::env::var("HOST")
        .expect("HOST is set in .env")
        .parse()
        .expect("HOST is not in the correct format");
    
    let port: u16 = std::env::var("PORT")
        .expect("PORT must be set in .env")
        .parse()
        .expect("PORT is not the correct format");

    let addr = SocketAddr::from((host, port));

    // CORS configuration for NextJS frontend
    let cors = CorsLayer::new()
        .allow_origin(Any)  // In production, use specific origins
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        // Root and health
        .route("/", get(|| async { "NBA Stats API - v1.0" }))
        .route("/health", get(routes::health::health_check))

        // Player endpoints
        .route("/api/players", get(routes::players::get_players))
        .route("/api/players/{id}", get(routes::players::get_player_by_id))
        .route("/api/players/search", get(routes::players::search_players))
        .route("/api/players/{id}/shooting-zones", get(routes::players::get_player_shooting_zones))
        .route("/api/players/{id}/assist-zones", get(routes::players::get_player_assist_zones))
        .route("/api/players/{id}/play-types", get(routes::players::get_player_play_types))
        .route("/api/players/{id}/game-logs", get(routes::players::get_player_game_logs))
        .route("/api/players/{id}/props", get(routes::props::get_player_props))
        .route("/api/players/{id}/play-type-matchup", get(routes::players::get_player_play_type_matchup))
        .route("/api/players/{id}/assist-zone-matchup", get(routes::players::get_player_assist_zone_matchup))

        // Team endpoints
        .route("/api/teams", get(routes::teams::get_teams))
        .route("/api/teams/search", get(routes::teams::search_team))
        .route("/api/teams/{id}", get(routes::teams::get_team_by_id))
        .route("/api/teams/{id}/defensive-zones", get(routes::zones::get_team_defensive_zones))
        .route("/api/teams/{id}/defensive-play-types", get(routes::play_types::get_team_defensive_play_types))

        // Schedule endpoints
        .route("/api/schedule", get(routes::schedule::get_schedule))
        .route("/api/schedule/today", get(routes::schedule::get_todays_games))
        .route("/api/schedule/upcoming", get(routes::schedule::get_upcoming_games))
        .route("/api/schedule/upcoming/rosters", get(routes::schedule::get_upcoming_rosters))

        .layer(cors)
        .layer(TraceLayer::new_for_http())
        .with_state(pool);

    let listener= tokio::net::TcpListener::bind(addr)
        .await
        .expect("Failed to bind to address");

    tracing::info!("Server listening on {}", addr);

    axum::serve(listener, app)
    .await
    .expect("Failed to start server.");
}