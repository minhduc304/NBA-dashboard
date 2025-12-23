use sqlx::sqlite::SqlitePool;
use crate::models::*;

// Team queries
pub async fn get_all_teams(pool: &SqlitePool) -> Result<Vec<Team>, sqlx::Error> {
    sqlx::query_as::<_, Team>(
        r#"SELECT * FROM teams ORDER BY full_name"#
    )
    .fetch_all(pool)
    .await
}

pub async fn get_team_by_id(pool: &SqlitePool, team_id: i64) -> Result<Option<Team>, sqlx::Error> {
    sqlx::query_as::<_, Team>(
        r#"SELECT * FROM teams WHERE team_id = ?"#
    )
    .bind(team_id)
    .fetch_optional(pool)
    .await
}

pub async fn get_team_by_abbreviation(pool: &SqlitePool, abbreviation: &str) -> Result<Option<Team>, sqlx::Error> {
    sqlx::query_as::<_, Team>(
        r#"SELECT * FROM teams WHERE abbreviation = ?"#
    )
    .bind(abbreviation)
    .fetch_optional(pool)
    .await
}

// Player queries
pub async fn get_all_players(pool: &SqlitePool) -> Result<Vec<PlayerStats>, sqlx::Error> {
    sqlx::query_as::<_, PlayerStats>(
        r#"SELECT * FROM player_stats ORDER BY player_name"#
    )
    .fetch_all(pool)
    .await
}

pub async fn get_player_by_id(pool: &SqlitePool, player_id: i64) -> Result<Option<PlayerStats>, sqlx::Error> {
    sqlx::query_as::<_, PlayerStats>(
        r#"SELECT * FROM player_stats WHERE player_id = ?"#
    )
    .bind(player_id)
    .fetch_optional(pool)
    .await
}

pub async fn search_players(pool: &SqlitePool, player_name: &str) -> Result<Option<PlayerStats>, sqlx::Error> {
    sqlx::query_as::<_, PlayerStats>(
        r#"SELECT * FROM player_stats WHERE player_name = ?"#
    )
    .bind(player_name)
    .fetch_optional(pool)
    .await
}

// Zone queries - return all zones for a player
pub async fn get_shooting_zones(pool: &SqlitePool, player_id: i64) -> Result<Vec<PlayerShootingZones>, sqlx::Error> {
    sqlx::query_as::<_, PlayerShootingZones>(
        r#"SELECT * FROM player_shooting_zones WHERE player_id = ? ORDER BY zone_name"#
    )
    .bind(player_id)
    .fetch_all(pool)
    .await
}

pub async fn get_assist_zones(pool: &SqlitePool, player_id: i64) -> Result<Vec<PlayerAssistZones>, sqlx::Error> {
    sqlx::query_as::<_, PlayerAssistZones>(
        r#"SELECT * FROM player_assist_zones WHERE player_id = ? ORDER BY assists DESC"#
    )
    .bind(player_id)
    .fetch_all(pool)
    .await
}

// Play type queries - return all play types for a player
pub async fn get_player_playtypes(pool: &SqlitePool, player_id: i64) -> Result<Vec<PlayerPlayTypes>, sqlx::Error> {
    sqlx::query_as::<_, PlayerPlayTypes>(
        r#"SELECT * FROM player_play_types WHERE player_id = ? ORDER BY points_per_game DESC"#
    )
    .bind(player_id)
    .fetch_all(pool)
    .await
}

// Team defensive queries
pub async fn get_defensive_zones(pool: &SqlitePool, team_id: i64) -> Result<Vec<TeamDefensiveZones>, sqlx::Error> {
    sqlx::query_as::<_, TeamDefensiveZones>(
        r#"SELECT * FROM team_defensive_zones WHERE team_id = ? ORDER BY zone_name"#
    )
    .bind(team_id)
    .fetch_all(pool)
    .await
}

pub async fn get_defensive_play_types(pool: &SqlitePool, team_id: i64) -> Result<Vec<TeamDefensivePlayTypes>, sqlx::Error> {
    sqlx::query_as::<_, TeamDefensivePlayTypes>(
        r#"SELECT * FROM team_defensive_play_types WHERE team_id = ? ORDER BY ppp ASC"#
    )
    .bind(team_id)
    .fetch_all(pool)
    .await
}

// Schedule queries - read from cached SQLite data
pub async fn get_schedule_by_date(pool: &SqlitePool, date: &str) -> Result<Vec<ScheduleRow>, sqlx::Error> {
    sqlx::query_as::<_, ScheduleRow>(
        r#"SELECT * FROM schedule WHERE game_date = ? ORDER BY game_time"#
    )
    .bind(date)
    .fetch_all(pool)
    .await
}

pub async fn get_todays_schedule(pool: &SqlitePool) -> Result<Vec<ScheduleRow>, sqlx::Error> {
    let today = chrono::Local::now().format("%Y-%m-%d").to_string();
    get_schedule_by_date(pool, &today).await
}

pub async fn get_schedule_by_team(pool: &SqlitePool, team_abbreviation: &str) -> Result<Vec<ScheduleRow>, sqlx::Error> {
    sqlx::query_as::<_, ScheduleRow>(
        r#"SELECT * FROM schedule
           WHERE home_team_abbreviation = ? OR away_team_abbreviation = ?
           ORDER BY game_date, game_time"#
    )
    .bind(team_abbreviation)
    .bind(team_abbreviation)
    .fetch_all(pool)
    .await
}

pub async fn get_upcoming_schedule(pool: &SqlitePool, days: i32) -> Result<Vec<ScheduleRow>, sqlx::Error> {
    let today = chrono::Local::now().format("%Y-%m-%d").to_string();
    let end_date = (chrono::Local::now() + chrono::Duration::days(days as i64))
        .format("%Y-%m-%d")
        .to_string();

    sqlx::query_as::<_, ScheduleRow>(
        r#"SELECT * FROM schedule
           WHERE game_date >= ? AND game_date <= ?
           ORDER BY game_date, game_time"#
    )
    .bind(&today)
    .bind(&end_date)
    .fetch_all(pool)
    .await
}

/// Get the next game day (today, tomorrow, or the next day with games)
pub async fn get_next_game_day_schedule(pool: &SqlitePool) -> Result<Vec<ScheduleRow>, sqlx::Error> {
    let now = chrono::Local::now();
    let today = now.format("%Y-%m-%d").to_string();

    // First, try to get today's games
    let today_rows = sqlx::query_as::<_, ScheduleRow>(
        r#"SELECT * FROM schedule
           WHERE game_date = ?
           ORDER BY game_time"#
    )
    .bind(&today)
    .fetch_all(pool)
    .await?;

    if !today_rows.is_empty() {
        return Ok(today_rows);
    }

    // If no games today, try tomorrow
    let tomorrow = (now + chrono::Duration::days(1))
        .format("%Y-%m-%d")
        .to_string();

    let tomorrow_rows = sqlx::query_as::<_, ScheduleRow>(
        r#"SELECT * FROM schedule
           WHERE game_date = ?
           ORDER BY game_time"#
    )
    .bind(&tomorrow)
    .fetch_all(pool)
    .await?;

    if !tomorrow_rows.is_empty() {
        return Ok(tomorrow_rows);
    }

    // If no games today or tomorrow, find the next day with games within next 14 days
    let end_date = (now + chrono::Duration::days(14))
        .format("%Y-%m-%d")
        .to_string();

    sqlx::query_as::<_, ScheduleRow>(
        r#"SELECT * FROM schedule
           WHERE game_date > ?
           AND game_date <= ?
           ORDER BY game_date, game_time
           LIMIT 20"# // Reasonable limit for a single day's games
    )
    .bind(&today)
    .bind(&end_date)
    .fetch_all(pool)
    .await
}

/// Get players for a specific team (with injury status if available)
pub async fn get_team_roster(pool: &SqlitePool, team_id: i64) -> Result<Vec<RosterPlayerRow>, sqlx::Error> {
    sqlx::query_as::<_, RosterPlayerRow>(
        r#"SELECT
               ps.player_id,
               ps.player_name,
               ps.position,
               pi.injury_status,
               pi.injury_description
           FROM player_stats ps
           LEFT JOIN player_injuries pi ON ps.player_id = pi.player_id
           WHERE ps.team_id = ?
           ORDER BY
               CASE ps.position
                   WHEN 'C' THEN 1
                   WHEN 'C-F' THEN 2
                   WHEN 'F-C' THEN 3
                   WHEN 'F' THEN 4
                   WHEN 'G-F' THEN 5
                   WHEN 'F-G' THEN 6
                   WHEN 'G' THEN 7
                   ELSE 8
               END,
               ps.points DESC"#
    )
    .bind(team_id)
    .fetch_all(pool)
    .await
}

/// Get game logs for a specific player
pub async fn get_player_game_logs(pool: &SqlitePool, player_id: i64, limit: i64) -> Result<Vec<PlayerGameLog>, sqlx::Error> {
    sqlx::query_as::<_, PlayerGameLog>(
        r#"SELECT
               game_id,
               player_id,
               team_id,
               season,
               game_date,
               matchup,
               min,
               pts,
               reb,
               ast,
               stl,
               blk,
               fg3m,
               tov
           FROM player_game_logs
           WHERE player_id = ?
           ORDER BY game_date DESC
           LIMIT ?"#
    )
    .bind(player_id)
    .bind(limit)
    .fetch_all(pool)
    .await
}

