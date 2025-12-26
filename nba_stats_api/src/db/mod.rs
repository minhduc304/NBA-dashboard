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

/// Get today + tomorrow schedule combined (for upcoming rosters endpoint)
pub async fn get_upcoming_schedule_for_roster(pool: &SqlitePool) -> Result<Vec<ScheduleRow>, sqlx::Error> {
    let today = chrono::Local::now().format("%Y-%m-%d").to_string();
    let tomorrow = (chrono::Local::now() + chrono::Duration::days(1))
        .format("%Y-%m-%d")
        .to_string();
    sqlx::query_as::<_, ScheduleRow>(
        r#"SELECT * FROM schedule
           WHERE game_date IN (?, ?)
           ORDER BY game_date, game_time"#
    )
    .bind(&today)
    .bind(&tomorrow)
    .fetch_all(pool)
    .await
}

/// Get players for a specific team (with injury status and props availability)
pub async fn get_team_roster(pool: &SqlitePool, team_id: i64) -> Result<Vec<RosterPlayerRow>, sqlx::Error> {
    sqlx::query_as::<_, RosterPlayerRow>(
        r#"SELECT
               ps.player_id,
               ps.player_name,
               ps.position,
               pi.injury_status,
               pi.injury_description,
               (SELECT 1 FROM underdog_props WHERE full_name = ps.player_name LIMIT 1) IS NOT NULL as has_props
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

/// Get underdog props for a player by name (for tomorrow's games)
/// Only returns the latest version of each line (by updated_at timestamp)
pub async fn get_player_props(pool: &SqlitePool, player_name: &str) -> Result<Vec<UnderdogProp>, sqlx::Error> {
    let tomorrow = (chrono::Local::now() + chrono::Duration::days(1))
        .format("%Y-%m-%d")
        .to_string();

    sqlx::query_as::<_, UnderdogProp>(
        r#"SELECT id, full_name, team_name, opponent_name, stat_name, stat_value,
                  choice, american_price, decimal_price, scheduled_at
           FROM (
               SELECT id, full_name, team_name, opponent_name, stat_name, stat_value,
                      choice, american_price, decimal_price, scheduled_at,
                      ROW_NUMBER() OVER (
                          PARTITION BY stat_name, choice
                          ORDER BY updated_at DESC
                      ) as rn
               FROM underdog_props
               WHERE full_name = ? AND DATE(scheduled_at) = ?
           )
           WHERE rn = 1
           ORDER BY stat_name, choice"#
    )
    .bind(player_name)
    .bind(&tomorrow)
    .fetch_all(pool)
    .await
}

/// Get underdog props for a player by ID (looks up name first)
pub async fn get_player_props_by_id(pool: &SqlitePool, player_id: i64) -> Result<Vec<UnderdogProp>, sqlx::Error> {
    // First get the player name
    let player = get_player_by_id(pool, player_id).await?;

    match player {
        Some(p) => get_player_props(pool, &p.player_name).await,
        None => Ok(vec![]),
    }
}

/// Get team defensive play type rankings (1 = best defense, 30 = worst)
pub async fn get_team_defensive_play_type_ranks(pool: &SqlitePool) -> Result<std::collections::HashMap<(i64, String), i32>, sqlx::Error> {
    // Get all team defensive play types ordered by PPP (lower = better defense)
    let rows = sqlx::query_as::<_, (i64, String, f32)>(
        r#"SELECT team_id, play_type, ppp FROM team_defensive_play_types ORDER BY play_type, ppp ASC"#
    )
    .fetch_all(pool)
    .await?;

    // Group by play_type and assign ranks
    let mut ranks: std::collections::HashMap<(i64, String), i32> = std::collections::HashMap::new();
    let mut current_play_type = String::new();
    let mut rank = 0;

    for (team_id, play_type, _ppp) in rows {
        if play_type != current_play_type {
            current_play_type = play_type.clone();
            rank = 0;
        }
        rank += 1;
        ranks.insert((team_id, play_type), rank);
    }

    Ok(ranks)
}

