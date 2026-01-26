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

/// Get team pace and ratings from team_pace table
pub async fn get_team_stats(pool: &SqlitePool, team_id: i64) -> Result<Option<crate::models::TeamStats>, sqlx::Error> {
    sqlx::query_as::<_, crate::models::TeamStats>(
        r#"SELECT team_id, season, pace, off_rating, def_rating, net_rating, games_played, wins, losses
           FROM team_pace
           WHERE team_id = ? AND season = '2025-26'"#
    )
    .bind(team_id)
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
        r#"SELECT player_id, season, zone_name, ast, fgm, fga, last_updated
           FROM player_assist_zones WHERE player_id = ? ORDER BY ast DESC"#
    )
    .bind(player_id)
    .fetch_all(pool)
    .await
}

pub async fn get_assist_zones_with_team_defense(
    pool: &SqlitePool,
    player_id: i64,
    opponent_team_id: i64
) -> Result<crate::models::AssistZoneMatchupResponse, sqlx::Error> {
    use crate::models::{AssistZoneMatchup, AssistZoneMatchupResponse};

    // Get player name
    let player_name: String = sqlx::query_scalar(
        r#"SELECT player_name FROM player_stats WHERE player_id = ? LIMIT 1"#
    )
    .bind(player_id)
    .fetch_one(pool)
    .await?;

    // Get opponent team name
    let opponent_name: String = sqlx::query_scalar(
        r#"SELECT full_name FROM teams WHERE team_id = ? LIMIT 1"#
    )
    .bind(opponent_team_id)
    .fetch_one(pool)
    .await?;

    // Get player's assist zones
    let player_zones = get_assist_zones(pool, player_id).await?;

    // Calculate total assists
    let total_assists: i64 = player_zones.iter().map(|z| z.assists).sum();

    // Get opponent's defensive zones
    let opponent_def_zones = get_defensive_zones(pool, opponent_team_id).await?;

    // Get all team defensive zones to calculate rankings
    let all_team_zones: Vec<(i64, String, f32)> = sqlx::query_as(
        r#"SELECT team_id, zone_name, opp_fg_pct FROM team_defensive_zones ORDER BY zone_name, opp_fg_pct"#
    )
    .fetch_all(pool)
    .await?;

    // Build zone matchups
    let mut zones: Vec<AssistZoneMatchup> = Vec::new();

    for player_zone in player_zones.iter() {
        // Find opponent's defensive FG% for this zone
        let opp_def = opponent_def_zones.iter()
            .find(|z| z.zone_name == player_zone.zone_name);

        let (opp_def_fg_pct, opp_def_rank, has_data) = if let Some(def_zone) = opp_def {
            // Calculate ranking: count how many teams have lower FG% (better defense)
            let rank = all_team_zones.iter()
                .filter(|(_, zone, fg_pct)| zone == &player_zone.zone_name && fg_pct < &def_zone.opp_fg_pct)
                .count() as i32 + 1;

            (def_zone.opp_fg_pct, rank, true)
        } else {
            (0.0, 0, false)
        };

        let player_ast_pct = if total_assists > 0 {
            (player_zone.assists as f32 / total_assists as f32) * 100.0
        } else {
            0.0
        };

        zones.push(AssistZoneMatchup {
            zone_name: player_zone.zone_name.clone(),
            player_assists: player_zone.assists,
            player_ast_pct,
            opp_def_rank,
            opp_def_fg_pct,
            has_data,
        });
    }

    Ok(AssistZoneMatchupResponse {
        player_name,
        opponent_name,
        total_assists,
        zones,
    })
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

/// Get shooting zone matchup with league context (league averages, opponent ranks, volume)
pub async fn get_shooting_zone_matchup(
    pool: &SqlitePool,
    player_id: i64,
    opponent_team_id: i64
) -> Result<crate::models::ShootingZoneMatchupResponse, sqlx::Error> {
    use crate::models::{ShootingZoneMatchup, ShootingZoneMatchupResponse};

    // Get player name
    let player_name: String = sqlx::query_scalar(
        r#"SELECT player_name FROM player_stats WHERE player_id = ? LIMIT 1"#
    )
    .bind(player_id)
    .fetch_optional(pool)
    .await?
    .unwrap_or_else(|| "Unknown".to_string());

    // Get opponent team name
    let opponent_name: String = sqlx::query_scalar(
        r#"SELECT full_name FROM teams WHERE team_id = ? LIMIT 1"#
    )
    .bind(opponent_team_id)
    .fetch_optional(pool)
    .await?
    .unwrap_or_else(|| "Unknown".to_string());

    // Get player's shooting zones
    let player_zones = get_shooting_zones(pool, player_id).await?;

    // Calculate player's total FGA
    let total_fga: f32 = player_zones.iter().map(|z| z.fga).sum();

    // Get opponent's defensive zones
    let opponent_def_zones = get_defensive_zones(pool, opponent_team_id).await?;

    // Get all team defensive zones to calculate league averages and rankings
    #[derive(sqlx::FromRow)]
    struct ZoneDefense {
        team_id: i64,
        zone_name: String,
        opp_fg_pct: f32,
    }
    let all_def_zones: Vec<ZoneDefense> = sqlx::query_as(
        r#"SELECT team_id, zone_name, opp_fg_pct FROM team_defensive_zones ORDER BY zone_name, opp_fg_pct"#
    )
    .fetch_all(pool)
    .await?;

    // Zone names and whether they're 3-point zones
    let zone_names = [
        ("Above the Break 3", true),
        ("In The Paint (Non-RA)", false),
        ("Left Corner 3", true),
        ("Mid-Range", false),
        ("Restricted Area", false),
        ("Right Corner 3", true),
    ];

    let mut zones = Vec::new();

    for (zone_name, is_three) in zone_names.iter() {
        let player_zone = player_zones.iter().find(|z| z.zone_name == *zone_name);
        let opp_zone = opponent_def_zones.iter().find(|z| z.zone_name == *zone_name);

        // Calculate league average for this zone
        let zone_defenses: Vec<&ZoneDefense> = all_def_zones
            .iter()
            .filter(|z| z.zone_name == *zone_name)
            .collect();

        let league_avg: f32 = if !zone_defenses.is_empty() {
            zone_defenses.iter().map(|z| z.opp_fg_pct).sum::<f32>() / zone_defenses.len() as f32
        } else {
            0.0
        };

        // Calculate opponent rank (1 = best defense = lowest opp_fg_pct)
        let opp_rank = if let Some(opp) = opp_zone {
            zone_defenses
                .iter()
                .position(|z| z.team_id == opponent_team_id)
                .map(|pos| (pos + 1) as i32)
                .unwrap_or(15)
        } else {
            15 // Default to middle if no data
        };

        let has_data = player_zone.is_some() && opp_zone.is_some();

        // Player FG% is already stored as percentage (38.9 = 38.9%)
        let player_fg_pct = player_zone.map(|z| z.fg_pct).unwrap_or(0.0);
        let player_fga = player_zone.map(|z| z.fga).unwrap_or(0.0);
        let player_fgm = player_zone.map(|z| z.fgm).unwrap_or(0.0);

        // Opponent FG% is stored as decimal (0.35 = 35%), convert to percentage
        let opp_fg_pct = opp_zone.map(|z| z.opp_fg_pct * 100.0).unwrap_or(0.0);
        let league_avg_pct = league_avg * 100.0;

        // Calculate player's volume percentage
        let player_volume_pct = if total_fga > 0.0 {
            (player_fga / total_fga) * 100.0
        } else {
            0.0
        };

        // League-adjusted advantage:
        // playerVsLeague = how much better/worse player is vs league avg
        // oppVsLeague = how much more/less opponent allows vs league avg (positive = bad defense)
        // advantage = playerVsLeague + oppVsLeague
        let player_vs_league = player_fg_pct - league_avg_pct;
        let opp_vs_league = opp_fg_pct - league_avg_pct; // positive = allows more = bad defense
        let advantage = player_vs_league + opp_vs_league;

        zones.push(ShootingZoneMatchup {
            zone_name: zone_name.to_string(),
            player_fgm,
            player_fga,
            player_fg_pct,
            player_volume_pct,
            opp_fg_pct,
            opp_rank,
            league_avg_pct,
            advantage,
            is_three: *is_three,
            has_data,
        });
    }

    Ok(ShootingZoneMatchupResponse {
        player_name,
        player_id,
        opponent_name,
        opponent_id: opponent_team_id,
        total_fga,
        zones,
    })
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
               (SELECT 1 FROM underdog_props
                WHERE (full_name = ps.player_name
                       OR full_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                           ps.player_name, 'ć', 'c'), 'č', 'c'), 'š', 's'), 'ž', 'z'), 'đ', 'd'))
                AND DATE(scheduled_at) >= DATE('now')
                LIMIT 1) IS NOT NULL as has_props
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
               pgl.game_id,
               pgl.player_id,
               pgl.team_id,
               pgl.season,
               pgl.game_date,
               pgl.matchup,
               CASE
                   WHEN s.home_score IS NOT NULL AND s.away_score IS NOT NULL THEN
                       CASE
                           WHEN pgl.team_id = s.home_team_id THEN
                               CASE WHEN s.home_score > s.away_score THEN 'W' ELSE 'L' END
                           ELSE
                               CASE WHEN s.away_score > s.home_score THEN 'W' ELSE 'L' END
                       END
                   ELSE NULL
               END as wl,
               pgl.min,
               pgl.pts,
               pgl.reb,
               pgl.ast,
               pgl.stl,
               pgl.blk,
               pgl.fgm,
               pgl.fga,
               pgl.fg3m,
               pgl.fg3a,
               pgl.ftm,
               pgl.fta,
               pgl.tov,
               CASE
                   WHEN s.home_score IS NOT NULL AND s.away_score IS NOT NULL THEN
                       CASE
                           WHEN pgl.team_id = s.home_team_id THEN s.home_score - s.away_score
                           ELSE s.away_score - s.home_score
                       END
                   ELSE NULL
               END as game_margin,
               pgl.oreb,
               pgl.dreb
           FROM player_game_logs pgl
           LEFT JOIN schedule s ON pgl.game_id = s.game_id
           WHERE pgl.player_id = ?
           ORDER BY pgl.game_date DESC
           LIMIT ?"#
    )
    .bind(player_id)
    .bind(limit)
    .fetch_all(pool)
    .await
}

/// Normalize a name by removing accents and special characters
/// Helps match "Luka Dončić" with "Luka Doncic"
fn normalize_name(name: &str) -> String {
    name.chars()
        .map(|c| match c {
            'á' | 'à' | 'ä' | 'â' | 'ã' => 'a',
            'é' | 'è' | 'ë' | 'ê' => 'e',
            'í' | 'ì' | 'ï' | 'î' => 'i',
            'ó' | 'ò' | 'ö' | 'ô' | 'õ' => 'o',
            'ú' | 'ù' | 'ü' | 'û' => 'u',
            'ć' | 'č' | 'ç' => 'c',
            'ñ' => 'n',
            'š' => 's',
            'ž' => 'z',
            'ý' | 'ÿ' => 'y',
            'đ' => 'd',
            'Á' | 'À' | 'Ä' | 'Â' | 'Ã' => 'A',
            'É' | 'È' | 'Ë' | 'Ê' => 'E',
            'Í' | 'Ì' | 'Ï' | 'Î' => 'I',
            'Ó' | 'Ò' | 'Ö' | 'Ô' | 'Õ' => 'O',
            'Ú' | 'Ù' | 'Ü' | 'Û' => 'U',
            'Ć' | 'Č' | 'Ç' => 'C',
            'Ñ' => 'N',
            'Š' => 'S',
            'Ž' => 'Z',
            'Ý' | 'Ÿ' => 'Y',
            'Đ' => 'D',
            _ => c,
        })
        .collect()
}

/// Get underdog props for a player by name (for today's or tomorrow's games)
/// Only returns the latest version of each line (by updated_at timestamp)
/// Tries exact match first, then normalized name match for accented characters
pub async fn get_player_props(pool: &SqlitePool, player_name: &str) -> Result<Vec<UnderdogProp>, sqlx::Error> {
    let today = chrono::Local::now().format("%Y-%m-%d").to_string();
    let tomorrow = (chrono::Local::now() + chrono::Duration::days(1))
        .format("%Y-%m-%d")
        .to_string();

    // Try exact match first
    let results = sqlx::query_as::<_, UnderdogProp>(
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
               WHERE full_name = ? AND DATE(scheduled_at) IN (?, ?)
           )
           WHERE rn = 1
           ORDER BY stat_name, choice"#
    )
    .bind(player_name)
    .bind(&today)
    .bind(&tomorrow)
    .fetch_all(pool)
    .await?;

    if !results.is_empty() {
        return Ok(results);
    }

    // Try normalized name (strips accents: Dončić -> Doncic)
    let normalized = normalize_name(player_name);
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
               WHERE full_name = ? AND DATE(scheduled_at) IN (?, ?)
           )
           WHERE rn = 1
           ORDER BY stat_name, choice"#
    )
    .bind(&normalized)
    .bind(&today)
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

/// Get DNP (Did Not Play) players for a specific game and team
/// Returns top 2 players who were on the roster but didn't play, sorted by season average
pub async fn get_dnp_players_for_game(
    pool: &SqlitePool,
    game_id: &str,
    team_id: i64,
    stat_column: &str,
) -> Result<Vec<crate::models::DnpPlayer>, sqlx::Error> {
    // Validate stat_column to prevent SQL injection
    let valid_stats = ["points", "assists", "rebounds", "threes_made", "threes_attempted", "fg_attempted",
                       "pts_plus_ast", "pts_plus_reb", "ast_plus_reb", "pts_plus_ast_plus_reb",
                       "steals", "blocks", "steals_plus_blocks", "turnovers"];

    if !valid_stats.contains(&stat_column) {
        // Return empty vec for invalid stat
        return Ok(vec![]);
    }

    // Build the query dynamically with the stat column
    let query = format!(
        r#"
        SELECT ps.player_id, ps.player_name, ps.position,
               COALESCE(ps.{}, 0.0) as season_avg
        FROM player_stats ps
        WHERE ps.team_id = ?
          AND ps.player_id NOT IN (
              SELECT CAST(player_id AS INTEGER)
              FROM player_game_logs
              WHERE game_id = ?
          )
        ORDER BY season_avg DESC
        LIMIT 2
        "#,
        stat_column
    );

    let rows = sqlx::query_as::<_, (i64, String, Option<String>, f32)>(&query)
        .bind(team_id)
        .bind(game_id)
        .fetch_all(pool)
        .await?;

    Ok(rows
        .into_iter()
        .map(|(player_id, player_name, position, season_avg)| crate::models::DnpPlayer {
            player_id,
            player_name,
            position,
            season_avg,
        })
        .collect())
}

