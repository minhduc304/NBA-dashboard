use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::Json,
};
use chrono::Timelike;
use chrono_tz::America::New_York;
use sqlx::sqlite::SqlitePool;
use std::collections::HashMap;
use crate::db;
use crate::models::{SharpBookLine, TopPick, TopPicksResponse};

#[derive(serde::Deserialize)]
pub struct ScreenerQuery {
    pub game_date: Option<String>,
}

/// Convert American odds to implied probability (0.0–1.0)
fn implied_prob(odds: i32) -> f64 {
    if odds < 0 {
        let o = odds.abs() as f64;
        o / (o + 100.0)
    } else {
        100.0 / (odds as f64 + 100.0)
    }
}

/// Devig over probability using multiplicative method.
/// Returns None if either side's odds are missing.
fn devigged_over_prob(over_odds: Option<i32>, under_odds: Option<i32>) -> Option<f64> {
    let over = implied_prob(over_odds?);
    let under = implied_prob(under_odds?);
    let total = over + under;
    if total < 0.001 {
        return None;
    }
    Some(over / total)
}

/// Check if a game has started based on its date and time (ET).
fn has_game_started(game_date: &str, game_time: &Option<String>) -> bool {
    let now_et = chrono::Utc::now().with_timezone(&New_York);
    let parsed_date = match chrono::NaiveDate::parse_from_str(game_date, "%Y-%m-%d") {
        Ok(d) => d,
        Err(_) => return false,
    };
    let today_et = now_et.date_naive();
    if parsed_date > today_et {
        return false;
    }
    if parsed_date < today_et {
        return true;
    }
    // Game is today — check time
    let time_str = match game_time {
        Some(t) if t != "TBD" && t != "Scheduled" && t != "12:00 AM" => t,
        _ => return false,
    };
    let re = regex::Regex::new(r"(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)").unwrap();
    let caps = match re.captures(time_str) {
        Some(c) => c,
        None => return false,
    };
    let mut hours: u32 = caps.get(1).unwrap().as_str().parse().unwrap_or(0);
    let minutes: u32 = caps.get(2).unwrap().as_str().parse().unwrap_or(0);
    let am_pm = caps.get(3).unwrap().as_str().to_uppercase();
    if am_pm == "PM" && hours != 12 {
        hours += 12;
    } else if am_pm == "AM" && hours == 12 {
        hours = 0;
    }
    now_et.hour() > hours || (now_et.hour() == hours && now_et.minute() >= minutes)
}

/// Intermediate: all book data grouped for one player+stat
struct CandidateGroup {
    player_name: String,
    stat_type: String,
    ud_line: f64,
    ud_odds: Option<i32>,
    home_team: String,
    away_team: String,
    game_date: String,
    books: Vec<SharpBookLine>,
}

/// GET /api/screener/top-picks?game_date=
pub async fn get_top_picks(
    State(pool): State<SqlitePool>,
    Query(params): Query<ScreenerQuery>,
) -> Result<Json<TopPicksResponse>, StatusCode> {
    let game_date = params.game_date.unwrap_or_else(|| {
        chrono::Local::now().format("%Y-%m-%d").to_string()
    });

    let all_rows = db::get_top_pick_candidates(&pool, &game_date)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Filter out rows for games that have already started
    let rows: Vec<_> = all_rows
        .into_iter()
        .filter(|row| !has_game_started(&row.game_date, &row.game_time))
        .collect();

    // Group rows by (player_name, stat_type)
    let mut groups: HashMap<(String, String), CandidateGroup> = HashMap::new();
    for row in rows {
        let key = (row.player_name.clone(), row.stat_type.clone());
        let group = groups.entry(key).or_insert_with(|| CandidateGroup {
            player_name: row.player_name.clone(),
            stat_type: row.stat_type.clone(),
            ud_line: row.ud_line,
            ud_odds: row.ud_odds,
            home_team: row.home_team.clone(),
            away_team: row.away_team.clone(),
            game_date: row.game_date.clone(),
            books: Vec::new(),
        });
        group.books.push(SharpBookLine {
            sportsbook: row.sportsbook,
            line: row.book_line,
            over_odds: row.over_odds,
            under_odds: row.under_odds,
        });
    }

    // For each group, find the best edge from books with the exact matching line
    let ud_default_odds = -110;
    let mut picks: Vec<TopPick> = groups
        .into_values()
        .filter_map(|group| {
            let ud_odds_val = group.ud_odds.unwrap_or(ud_default_odds);
            let ud_prob = implied_prob(ud_odds_val);

            // Find best devigged edge from books at the exact UD line
            let mut best_edge: f64 = 0.0;
            let mut best_book = String::new();
            let mut best_devigged = 0.0;

            for book in &group.books {
                if (book.line - group.ud_line).abs() < 0.01 {
                    if let Some(sharp_over) = devigged_over_prob(book.over_odds, book.under_odds) {
                        // Edge = sharp over prob - UD over implied prob
                        // Positive → sharp thinks over hits more often → take OVER
                        // Negative → sharp thinks under hits more often → take UNDER
                        let edge = sharp_over - ud_prob;

                        if edge.abs() > best_edge.abs() {
                            best_edge = edge;
                            best_book = book.sportsbook.clone();
                            // Store the fair prob for the direction we'd take
                            best_devigged = if edge > 0.0 { sharp_over } else { 1.0 - sharp_over };
                        }
                    }
                }
            }

            // Skip if no matching-line book found or edge is negligible
            if best_book.is_empty() || best_edge.abs() < 0.005 {
                return None;
            }

            let is_over = best_edge > 0.0;
            let direction = if is_over { "OVER" } else { "UNDER" };
            let edge_pct = (best_edge.abs() * 1000.0).round() / 10.0; // to 1 decimal %
            // Show UD implied prob for the direction we're taking
            let ud_dir_prob = if is_over { ud_prob } else { 1.0 - ud_prob };

            Some(TopPick {
                player_name: group.player_name,
                stat_type: group.stat_type,
                direction: direction.to_string(),
                ud_line: group.ud_line,
                ud_odds: group.ud_odds,
                ud_implied_prob: (ud_dir_prob * 1000.0).round() / 10.0,
                edge_pct,
                best_book,
                best_book_devigged_prob: (best_devigged * 1000.0).round() / 10.0,
                books: group.books,
                home_team: group.home_team,
                away_team: group.away_team,
                game_date: group.game_date,
            })
        })
        .collect();

    // Sort by edge descending, take top 10
    picks.sort_by(|a, b| b.edge_pct.partial_cmp(&a.edge_pct).unwrap_or(std::cmp::Ordering::Equal));
    picks.truncate(20);

    Ok(Json(TopPicksResponse {
        picks,
        last_updated: Some(game_date),
    }))
}
