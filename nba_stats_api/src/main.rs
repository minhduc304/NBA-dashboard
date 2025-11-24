use sqlx::sqlite::SqlitePool;
use axum::{routing::get, Router};
use std::net::{Ipv4Addr, SocketAddr};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

// TODO: Your main entry point goes here
//
// Learning objectives for this file:
// 1. Understand #[tokio::main] attribute
// 2. Learn how to set up Axum Router
// 3. Practice creating HTTP server with axum::Server
// 4. Learn about connection pooling with SQLx
//
// Hints:
// - You'll need to create a database connection pool
// - Pass the pool as shared state to your routes
// - Set up your Router with routes from other modules
// - Start the server listening on a port

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
    
    let app = Router::new()
        .route("/", get(|| async { "Hello, World!" }))
        .route("/health", get(health_check))
        .with_state(pool);

    let listener= tokio::net::TcpListener::bind(addr)
        .await
        .expect("Failed to bind to address");

    tracing::info!("Server listening on {}", addr);

    axum::serve(listener, app)
    .await
    .expect("Failed to start server.");
}

// Health check handler
async fn health_check() -> &'static str{
    "200 OK"
}