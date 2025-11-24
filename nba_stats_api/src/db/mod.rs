use sqlx::sqlite::SqlitePool;

// Maybe implement Path for ids 

// pub async fn get_all_players(pool: &SqlitePool) -> Result<Vec<PlayerStats>, sqlx::Error> {}

pub async fn get_player_by_id(pool: &SqlitePool, player_id: i64) -> Result<Option<PlayerStats>, sqlx::Error> {
    Ok(
        sqlx::query_as!(
            PlayerStats,
            r#"SELECT * FROM player_stats WHERE player_id = ?"#,
            player_id 
        )
        .fetch_optional(pool)
        .await?
    )
}


pub async fn search_players(pool: &SqlitePool, player_name: &str) -> Result<Option<PlayerStats>, sqlx::Error> {
    Ok(   
        sqlx::query_as!(
            PlayerStats,
            r#"SELECT * FROM player_stats WHERE player_name = ?"#,
            player_name
        )
        .fetch_optional(pool)
        .await?
    )
}

pub async fn get_shooting_zones(pool: &SqlitePool, player_id: i64) -> Result<Option<PlayerShootingZones>, sqlx::Error> {
    Ok(
        sqlx::query_as!(
            PlayerShootingZones,
            r#"SELECT * FROM player_shooting_zones WHERE player_id = ?"#,
            player_id
        )
        .fetch_optional(pool)
        .await?
    )
}

pub async fn get_assist_zones(pool: &SqlitePool, player_id: i64) -> Result<Option<PlayerAssistZones>, sqlx::Error> {
    Ok(
        sqlx::query_as!(
            PlayerAssistZones,
            r#"SELECT * FROM player_assist_zones WHERE player_id = ?"#,
            player_id
        )
        .fetch_optional(pool)
        .await?
    )
}

pub async fn get_player_playtypes(pool: &SqlitePool, player_id: i64) -> Result<Option<PlayerPlayTypes>, sqlx::Error> {
    Ok(
        sqlx::query_as!(
            PlayerPlayTypes,
            r#"SELECT * FROM player_play_types WHERE player_id = ?"#,
            player_id
        )
        .fetch_optional(pool)
        .await?
    )
}

pub async fn get_defensive_zones(pool: &SqlitePool, team_id: i64) -> Result<Vec<TeamDefensiveZones>, sqlx::Error> {
    Ok(
        sqlx::query_as!(
            TeamDefensiveZones,
            r#"SELECT * FROM team_defensive_zones WHERE team_id = ?"#,
            team_id
        )
        .fetch_one(pool)
        .await?
    )
}

pub async fn get_defense_against_playtypes(pool: &SqlitePool, team_id: i64) -> Result<Vec<TeamDefenseAgainstPlayTypes>, sqlx::Error> {
    Ok(
        sqlx::query_as!(
            TeamDefenseAgainstPlayTypes,
            r#"SELECT * FROM team_defensive_play_types WHERE team_id = ?"#,
            team_id
        )
        .fetch_one(pool)
        .await?
    )
}

