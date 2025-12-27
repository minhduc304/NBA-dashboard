use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::Json,
};
use chrono::Timelike;
use chrono_tz::America::New_York;
use serde::Deserialize;
use sqlx::sqlite::SqlitePool;
use crate::db;
use crate::models::{ScheduleResponse, ScheduleGame, RosterResponse, GameWithRosters, TeamInfo};

/// Query parameters for filtering schedule
#[derive(Deserialize)]
pub struct ScheduleQuery {
    /// Filter by date (format: YYYY-MM-DD)
    #[serde(default)]
    pub date: Option<String>,
    /// Filter by team abbreviation (e.g., "LAL", "BOS")
    #[serde(default)]
    pub team: Option<String>,
}

/// GET /api/schedule - Get NBA game schedule
///
/// Query params:
/// - date: Filter games by date (YYYY-MM-DD format)
/// - team: Filter games by team abbreviation
pub async fn get_schedule(
    State(pool): State<SqlitePool>,
    Query(params): Query<ScheduleQuery>,
) -> Result<Json<ScheduleResponse>, StatusCode> {
    let db_result = if let Some(date) = &params.date {
        db::get_schedule_by_date(&pool, date).await
    } else if let Some(team) = &params.team {
        db::get_schedule_by_team(&pool, team).await
    } else {
        db::get_todays_schedule(&pool).await
    };

    match db_result {
        Ok(rows) => {
            let games: Vec<ScheduleGame> = rows.iter().map(|r| r.to_schedule_game()).collect();
            let count = games.len();
            Ok(Json(ScheduleResponse { games, count }))
        }
        Err(e) => {
            tracing::error!("Failed to get schedule: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// GET /api/schedule/today - Get today's games
pub async fn get_todays_games(
    State(pool): State<SqlitePool>,
) -> Result<Json<ScheduleResponse>, StatusCode> {
    match db::get_todays_schedule(&pool).await {
        Ok(rows) => {
            let games: Vec<ScheduleGame> = rows.iter().map(|r| r.to_schedule_game()).collect();
            let count = games.len();
            Ok(Json(ScheduleResponse { games, count }))
        }
        Err(e) => {
            tracing::error!("Failed to get today's schedule: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// GET /api/schedule/upcoming - Get upcoming games for next 7 days
pub async fn get_upcoming_games(
    State(pool): State<SqlitePool>,
) -> Result<Json<ScheduleResponse>, StatusCode> {
    match db::get_upcoming_schedule(&pool, 7).await {
        Ok(rows) => {
            let games: Vec<ScheduleGame> = rows.iter().map(|r| r.to_schedule_game()).collect();
            let count = games.len();
            Ok(Json(ScheduleResponse { games, count }))
        }
        Err(e) => {
            tracing::error!("Failed to get upcoming schedule: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// Parse game time string (e.g., "7:30 PM" or "7:30 pm ET") into hour and minute
fn parse_game_time(time_str: &str) -> Option<(u32, u32)> {
    // Remove timezone indicator if present
    let clean_time = time_str
        .trim()
        .trim_end_matches("ET")
        .trim_end_matches("EST")
        .trim_end_matches("EDT")
        .trim();

    // Match pattern like "7:30 PM" or "10:00 AM"
    let re = regex::Regex::new(r"(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)").ok()?;
    let caps = re.captures(clean_time)?;

    let mut hours: u32 = caps.get(1)?.as_str().parse().ok()?;
    let minutes: u32 = caps.get(2)?.as_str().parse().ok()?;
    let am_pm = caps.get(3)?.as_str().to_uppercase();

    // Convert to 24-hour format
    if am_pm == "PM" && hours != 12 {
        hours += 12;
    } else if am_pm == "AM" && hours == 12 {
        hours = 0;
    }

    Some((hours, minutes))
}

/// Check if a game has started based on its date and time
/// Game times are in ET (Eastern Time), so we convert current time to ET for comparison
fn has_game_started(game_date: &str, game_time: &Option<String>) -> bool {
    // Get current time in ET (Eastern Time) since NBA game times are in ET
    let now_utc = chrono::Utc::now();
    let now_et = now_utc.with_timezone(&New_York);

    // Parse game date
    let parsed_date = chrono::NaiveDate::parse_from_str(game_date, "%Y-%m-%d");
    let game_date_parsed = match parsed_date {
        Ok(d) => d,
        Err(_) => return false, // Can't parse, assume not started
    };

    // Compare dates in ET
    let today_et = now_et.date_naive();
    if game_date_parsed > today_et {
        return false; // Game is in the future
    }

    // If game is before today (in ET), it has started (and finished)
    if game_date_parsed < today_et {
        return true;
    }

    // Game is today (in ET) - check the time
    let time_str = match game_time {
        Some(t) => t,
        None => return false, // No time info, assume not started
    };

    // Handle "TBD" or "Scheduled" - assume not started
    if time_str == "TBD" || time_str == "Scheduled" {
        return false;
    }

    let (game_hour, game_minute) = match parse_game_time(time_str) {
        Some((h, m)) => (h, m),
        None => return false, // Can't parse time, assume not started
    };

    // Compare current ET time with game time (both in ET now)
    let current_hour_et = now_et.hour();
    let current_minute_et = now_et.minute();

    if current_hour_et > game_hour {
        return true;
    } else if current_hour_et == game_hour && current_minute_et >= game_minute {
        return true;
    }

    false
}

/// GET /api/schedule/upcoming/rosters - Get upcoming games (today + tomorrow) with full player rosters
///
/// Returns today's and tomorrow's games that haven't started yet.
/// Games are filtered out once their scheduled start time has passed.
/// Each game includes full roster for both teams with player info and injury status.
pub async fn get_upcoming_rosters(
    State(pool): State<SqlitePool>,
) -> Result<Json<RosterResponse>, StatusCode> {
    // Get today + tomorrow games
    let schedule_rows = db::get_upcoming_schedule_for_roster(&pool)
        .await
        .map_err(|e| {
            tracing::error!("Failed to get upcoming schedule: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Filter out games that have already started
    let upcoming_games: Vec<_> = schedule_rows
        .into_iter()
        .filter(|game| !has_game_started(&game.game_date, &game.game_time))
        .collect();

    if upcoming_games.is_empty() {
        return Ok(Json(RosterResponse {
            games: vec![],
            count: 0,
        }));
    }

    let mut games_with_rosters = Vec::new();

    for game in &upcoming_games {
        // Get rosters for both teams
        let home_roster = db::get_team_roster(&pool, game.home_team_id)
            .await
            .map_err(|e| {
                tracing::error!("Failed to get home roster for team {}: {}", game.home_team_id, e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

        let away_roster = db::get_team_roster(&pool, game.away_team_id)
            .await
            .map_err(|e| {
                tracing::error!("Failed to get away roster for team {}: {}", game.away_team_id, e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

        games_with_rosters.push(GameWithRosters {
            game_id: game.game_id.clone(),
            game_date: game.game_date.clone(),
            game_time: game.game_time.clone().unwrap_or_else(|| "TBD".to_string()),
            game_status: game.game_status.clone().unwrap_or_default(),
            home_team: TeamInfo {
                id: game.home_team_id,
                name: game.home_team_name.clone().unwrap_or_default(),
                abbreviation: game.home_team_abbreviation.clone().unwrap_or_default(),
                city: game.home_team_city.clone().unwrap_or_default(),
            },
            away_team: TeamInfo {
                id: game.away_team_id,
                name: game.away_team_name.clone().unwrap_or_default(),
                abbreviation: game.away_team_abbreviation.clone().unwrap_or_default(),
                city: game.away_team_city.clone().unwrap_or_default(),
            },
            home_players: home_roster.iter().map(|r| r.to_roster_player()).collect(),
            away_players: away_roster.iter().map(|r| r.to_roster_player()).collect(),
        });
    }

    let count = games_with_rosters.len();
    Ok(Json(RosterResponse {
        games: games_with_rosters,
        count,
    }))
}
