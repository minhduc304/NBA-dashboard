use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::Json,
};
use sqlx::sqlite::SqlitePool;
use std::collections::HashMap;
use crate::db;
use crate::models::{BookLine, ConsensusInfo, ScreenerProp, ScreenerResponse};

#[derive(serde::Deserialize)]
pub struct ScreenerQuery {
    pub game_date: Option<String>,
    pub stat_type: Option<String>,
}

/// GET /api/screener/lines?game_date=&stat_type=
pub async fn get_screener_lines(
    State(pool): State<SqlitePool>,
    Query(params): Query<ScreenerQuery>,
) -> Result<Json<ScreenerResponse>, StatusCode> {
    let game_date = params.game_date.unwrap_or_else(|| {
        chrono::Local::now().format("%Y-%m-%d").to_string()
    });

    let rows = db::get_screener_lines(
        &pool,
        &game_date,
        params.stat_type.as_deref(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Track latest scraped_at across all rows
    let last_scraped = rows
        .iter()
        .filter_map(|r| r.scraped_at.as_ref())
        .max()
        .cloned();

    // Group rows by (player_name, stat_type)
    let mut grouped: HashMap<(String, String), Vec<&crate::models::ScreenerLineRow>> =
        HashMap::new();
    for row in &rows {
        grouped
            .entry((row.player_name.clone(), row.stat_type.clone()))
            .or_default()
            .push(row);
    }

    // Build ScreenerProp for each group
    let mut props: Vec<ScreenerProp> = grouped
        .into_iter()
        .map(|((player_name, stat_type), group_rows)| {
            let first = group_rows[0];
            let lines: Vec<f64> = group_rows.iter().map(|r| r.line).collect();
            let min_line = lines.iter().cloned().fold(f64::INFINITY, f64::min);
            let max_line = lines.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            let avg_line = lines.iter().sum::<f64>() / lines.len() as f64;

            let books: Vec<BookLine> = group_rows
                .iter()
                .map(|r| BookLine {
                    sportsbook: r.sportsbook.clone(),
                    line: r.line,
                    over_odds: r.over_odds,
                    under_odds: r.under_odds,
                })
                .collect();

            ScreenerProp {
                player_name,
                stat_type,
                game_date: first.game_date.clone(),
                home_team: first.home_team.clone(),
                away_team: first.away_team.clone(),
                consensus: ConsensusInfo {
                    avg_line: (avg_line * 10.0).round() / 10.0,
                    min_line,
                    max_line,
                    num_books: books.len(),
                },
                books,
            }
        })
        .collect();

    // Sort by player name, then stat type
    props.sort_by(|a, b| {
        a.player_name
            .cmp(&b.player_name)
            .then(a.stat_type.cmp(&b.stat_type))
    });

    Ok(Json(ScreenerResponse {
        props,
        last_scraped,
    }))
}
