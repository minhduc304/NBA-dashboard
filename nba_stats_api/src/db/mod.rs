use sqlx::sqlite::SqlitePool;
use crate::models::*;

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

