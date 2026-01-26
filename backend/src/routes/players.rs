use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::Json,
};
use serde::Deserialize;
use sqlx::sqlite::SqlitePool;
use crate::models::{PlayerStats, PlayTypeMatchup, PlayTypeMatchupResponse, UpcomingMatchupResponse};
use crate::db;

// Query parameters for listing players
#[derive(Deserialize)]
pub struct ListPlayersQuery {
    #[serde(default)]
    limit: Option<i64>,
    #[serde(default)]
    offset: Option<i64>,
}

// Query parameters for searching players
#[derive(Deserialize)]
pub struct SearchQuery {
    name: String,
}

// GET /api/players - List all players
pub async fn get_players(
    State(pool): State<SqlitePool>,
    Query(params): Query<ListPlayersQuery>,
) -> Result<Json<Vec<PlayerStats>>, StatusCode> {
    // Get all players from database
    let players = db::get_all_players(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Apply pagination if provided
    let start = params.offset.unwrap_or(0) as usize;
    let end = params.limit.map(|l| start + l as usize).unwrap_or(players.len());

    let paginated = players.into_iter().skip(start).take(end - start).collect();

    Ok(Json(paginated))
}

// GET /api/players/:id - Get player by ID
pub async fn get_player_by_id(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<PlayerStats>, StatusCode> {
    let player = db::get_player_by_id(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(player))
}

// GET /api/players/search?name=LeBron - Search players by name
pub async fn search_players(
    State(pool): State<SqlitePool>,
    Query(params): Query<SearchQuery>,
) -> Result<Json<PlayerStats>, StatusCode> {
    let player = db::search_players(&pool, &params.name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(player))
}

// GET /api/players/:id/shooting-zones - Get player's shooting zones
pub async fn get_player_shooting_zones(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<Vec<crate::models::PlayerShootingZones>>, StatusCode> {
    let zones = db::get_shooting_zones(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if zones.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(Json(zones))
}

// GET /api/players/:player_id/shooting-zones/vs/:opponent_id - Get shooting zone matchup with league context
pub async fn get_player_shooting_zone_matchup(
    State(pool): State<SqlitePool>,
    Path((player_id, opponent_id)): Path<(i64, i64)>,
) -> Result<Json<crate::models::ShootingZoneMatchupResponse>, StatusCode> {
    let matchup = db::get_shooting_zone_matchup(&pool, player_id, opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(matchup))
}

// GET /api/players/:id/assist-zones - Get player's assist zones
pub async fn get_player_assist_zones(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<Vec<crate::models::PlayerAssistZones>>, StatusCode> {
    let zones = db::get_assist_zones(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if zones.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(Json(zones))
}

// GET /api/players/:id/play-types - Get player's play types breakdown
pub async fn get_player_play_types(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<Vec<crate::models::PlayerPlayTypes>>, StatusCode> {
    let play_types = db::get_player_playtypes(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if play_types.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(Json(play_types))
}

// Query parameters for game logs
#[derive(Deserialize)]
pub struct GameLogsQuery {
    /// Number of games to return (default: 20, max: 82)
    /// Matches the "games" slider in the frontend UI
    #[serde(default = "default_limit")]
    limit: i64,
    /// Stat category for DNP players (points, assists, rebounds, etc.)
    /// Used to determine which stat to show for DNP players
    stat_category: Option<String>,
}

fn default_limit() -> i64 {
    20
}

// GET /api/players/:id/game-logs - Get player's game-by-game stats with DNP players
pub async fn get_player_game_logs(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
    Query(params): Query<GameLogsQuery>,
) -> Result<Json<Vec<crate::models::GameLogWithDnp>>, StatusCode> {
    // Cap limit at 82 (max games in a season)
    let limit = params.limit.min(82);

    let game_logs = db::get_player_game_logs(&pool, player_id, limit)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Get the player's current team from player_stats
    let player_team_id: Option<i64> = sqlx::query_scalar(
        r#"SELECT team_id FROM player_stats WHERE player_id = ?"#
    )
    .bind(player_id)
    .fetch_optional(&pool)
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
    .flatten();

    // Get stat column name for DNP queries
    let stat_column = params.stat_category.as_deref().unwrap_or("points");

    // For each game, get DNP players from the SAME team (teammates)
    // DNP teammates affect playing time and usage for the player
    let mut logs_with_dnp = Vec::new();

    for game_log in game_logs {
        let dnp_players = if let Some(team_id) = player_team_id {
            db::get_dnp_players_for_game(&pool, &game_log.game_id, team_id, stat_column)
                .await
                .unwrap_or_default()
        } else {
            vec![]
        };

        logs_with_dnp.push(crate::models::GameLogWithDnp {
            game_log,
            dnp_players,
        });
    }

    Ok(Json(logs_with_dnp))
}

// Helper to get opponent team ID from a game
async fn get_opponent_team_id(
    pool: &SqlitePool,
    game_id: &str,
    player_team_id: Option<i64>,
) -> Result<Option<i64>, sqlx::Error> {
    if player_team_id.is_none() {
        return Ok(None);
    }

    let player_team = player_team_id.unwrap();

    let result: Option<(i64, i64)> = sqlx::query_as(
        r#"SELECT home_team_id, away_team_id FROM schedule WHERE game_id = ?"#
    )
    .bind(game_id)
    .fetch_optional(pool)
    .await?;

    Ok(result.and_then(|(home_id, away_id)| {
        if home_id == player_team {
            Some(away_id)
        } else {
            Some(home_id)
        }
    }))
}

// Query parameters for play type matchup
#[derive(Deserialize)]
pub struct PlayTypeMatchupQuery {
    opponent_id: i64,
}

// GET /api/players/:id/play-type-matchup?opponent_id=123 - Get player's play type matchup vs opponent
pub async fn get_player_play_type_matchup(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
    Query(params): Query<PlayTypeMatchupQuery>,
) -> Result<Json<PlayTypeMatchupResponse>, StatusCode> {
    // Get player info
    let player = db::get_player_by_id(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    // Get opponent team info
    let opponent = db::get_team_by_id(&pool, params.opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    // Get player play types
    let player_play_types = db::get_player_playtypes(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Get opponent defensive play types
    let opp_defense = db::get_defensive_play_types(&pool, params.opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Get all team defensive rankings
    let ranks = db::get_team_defensive_play_type_ranks(&pool)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Build matchup data
    let mut matchups: Vec<PlayTypeMatchup> = player_play_types
        .iter()
        .filter_map(|pt| {
            // Find opponent's defensive stats for this play type
            let opp_def = opp_defense.iter().find(|d| d.play_type == pt.play_type)?;
            let rank = ranks.get(&(params.opponent_id, pt.play_type.clone())).copied().unwrap_or(0);

            Some(PlayTypeMatchup {
                play_type: pt.play_type.clone(),
                player_ppg: pt.points_per_game,
                pct_of_total: pt.pct_of_total_points,
                opp_ppp: opp_def.ppp,
                opp_rank: rank,
            })
        })
        .collect();

    // Sort by player PPG descending
    matchups.sort_by(|a, b| b.player_ppg.partial_cmp(&a.player_ppg).unwrap_or(std::cmp::Ordering::Equal));

    Ok(Json(PlayTypeMatchupResponse {
        player_name: player.player_name,
        opponent_name: opponent.full_name,
        matchups,
    }))
}

// Query parameters for assist zone matchup
#[derive(Deserialize)]
pub struct AssistZoneMatchupQuery {
    opponent_id: i64,
}

// GET /api/players/:id/assist-zone-matchup?opponent_id=123 - Get player's assist zone matchup vs opponent
pub async fn get_player_assist_zone_matchup(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
    Query(params): Query<AssistZoneMatchupQuery>,
) -> Result<Json<crate::models::AssistZoneMatchupResponse>, StatusCode> {
    let matchup = db::get_assist_zones_with_team_defense(&pool, player_id, params.opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(matchup))
}

// Query parameters for upcoming matchup context
#[derive(Deserialize)]
pub struct UpcomingMatchupQuery {
    opponent_id: i64,
    stat_type: String, // "points", "assists", "rebounds"
}

// GET /api/players/:id/upcoming-matchup?opponent_id=123&stat_type=points
// Get aggregated defensive context for upcoming game tooltip
pub async fn get_upcoming_matchup_context(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
    Query(params): Query<UpcomingMatchupQuery>,
) -> Result<Json<UpcomingMatchupResponse>, StatusCode> {
    // Get opponent team name
    let opponent = db::get_team_by_id(&pool, params.opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    // Get team stats (DefRtg, Pace)
    let team_stats = db::get_team_stats(&pool, params.opponent_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let def_rtg = team_stats.as_ref().and_then(|s| s.def_rating);
    let pace = team_stats.as_ref().and_then(|s| s.pace);

    let mut response = UpcomingMatchupResponse {
        opponent_name: opponent.full_name,
        stat_type: params.stat_type.clone(),
        def_rtg,
        pace,
        dsz_rank: None,
        dsz_name: None,
        dsz2_rank: None,
        dsz2_name: None,
        dpt_rank: None,
        dpt_name: None,
        dpt2_rank: None,
        dpt2_name: None,
        daz_rank: None,
        daz_name: None,
        daz2_rank: None,
        daz2_name: None,
        assists_allowed: None,
        rebounds_allowed: None,
        oreb_allowed: None,
        dreb_allowed: None,
    };

    match params.stat_type.as_str() {
        "points" => {
            // Get shooting zone matchup data
            if let Ok(zone_matchup) = db::get_shooting_zone_matchup(&pool, player_id, params.opponent_id).await {
                // Sort zones by FGA (volume) to find dominant zones
                let mut zones_by_volume: Vec<_> = zone_matchup.zones.iter()
                    .filter(|z| z.has_data && z.player_fga > 0.0)
                    .collect();
                zones_by_volume.sort_by(|a, b| b.player_fga.partial_cmp(&a.player_fga).unwrap_or(std::cmp::Ordering::Equal));

                if let Some(dsz) = zones_by_volume.first() {
                    response.dsz_name = Some(dsz.zone_name.clone());
                    response.dsz_rank = Some(dsz.opp_rank);
                }
                if let Some(dsz2) = zones_by_volume.get(1) {
                    response.dsz2_name = Some(dsz2.zone_name.clone());
                    response.dsz2_rank = Some(dsz2.opp_rank);
                }
            }

            // Get play type matchup data
            let player_play_types = db::get_player_playtypes(&pool, player_id)
                .await
                .unwrap_or_default();
            let opp_defense = db::get_defensive_play_types(&pool, params.opponent_id)
                .await
                .unwrap_or_default();
            let ranks = db::get_team_defensive_play_type_ranks(&pool)
                .await
                .unwrap_or_default();

            // Sort by pct_of_total_points to find dominant play types
            let mut play_types_by_pct: Vec<_> = player_play_types.iter()
                .filter(|pt| opp_defense.iter().any(|d| d.play_type == pt.play_type))
                .collect();
            play_types_by_pct.sort_by(|a, b| b.pct_of_total_points.partial_cmp(&a.pct_of_total_points).unwrap_or(std::cmp::Ordering::Equal));

            if let Some(dpt) = play_types_by_pct.first() {
                response.dpt_name = Some(dpt.play_type.clone());
                response.dpt_rank = ranks.get(&(params.opponent_id, dpt.play_type.clone())).copied();
            }
            if let Some(dpt2) = play_types_by_pct.get(1) {
                response.dpt2_name = Some(dpt2.play_type.clone());
                response.dpt2_rank = ranks.get(&(params.opponent_id, dpt2.play_type.clone())).copied();
            }
        },
        "assists" => {
            // Get assist zone matchup data
            if let Ok(assist_matchup) = db::get_assist_zones_with_team_defense(&pool, player_id, params.opponent_id).await {
                // Zones are already sorted by assists DESC
                if let Some(daz) = assist_matchup.zones.first() {
                    response.daz_name = Some(daz.zone_name.clone());
                    response.daz_rank = Some(daz.opp_def_rank);
                }
                if let Some(daz2) = assist_matchup.zones.get(1) {
                    response.daz2_name = Some(daz2.zone_name.clone());
                    response.daz2_rank = Some(daz2.opp_def_rank);
                }
            }

            // Get assists allowed by opponent (average from game logs)
            let assists_allowed: Option<f32> = sqlx::query_scalar(
                r#"SELECT CAST(AVG(ast) AS REAL) FROM player_game_logs
                   WHERE team_id != ? AND game_id IN (
                       SELECT game_id FROM schedule
                       WHERE home_team_id = ? OR away_team_id = ?
                   )"#
            )
            .bind(params.opponent_id)
            .bind(params.opponent_id)
            .bind(params.opponent_id)
            .fetch_optional(&pool)
            .await
            .ok()
            .flatten();

            response.assists_allowed = assists_allowed;
        },
        "rebounds" => {
            // Calculate team rebounding allowed per game for all teams
            // Then rank the opponent team
            #[derive(sqlx::FromRow)]
            struct TeamRebStats {
                team_id: i64,
                reb_allowed: f32,
                oreb_allowed: f32,
                dreb_allowed: f32,
            }

            // Get average rebounds allowed per game for each team
            // This sums player rebounds by game (for opposing team), then averages across games
            let all_team_reb_stats: Vec<TeamRebStats> = sqlx::query_as(
                r#"WITH game_rebounds AS (
                    SELECT
                        s.game_id,
                        CASE WHEN pgl.team_id = s.home_team_id THEN s.away_team_id ELSE s.home_team_id END as defending_team_id,
                        SUM(pgl.reb) as total_reb,
                        SUM(pgl.oreb) as total_oreb,
                        SUM(pgl.dreb) as total_dreb
                    FROM player_game_logs pgl
                    JOIN schedule s ON pgl.game_id = s.game_id
                    WHERE pgl.reb IS NOT NULL
                    GROUP BY s.game_id, defending_team_id
                )
                SELECT
                    defending_team_id as team_id,
                    CAST(AVG(total_reb) AS REAL) as reb_allowed,
                    CAST(AVG(total_oreb) AS REAL) as oreb_allowed,
                    CAST(AVG(total_dreb) AS REAL) as dreb_allowed
                FROM game_rebounds
                GROUP BY defending_team_id
                ORDER BY reb_allowed ASC"#
            )
            .fetch_all(&pool)
            .await
            .unwrap_or_default();

            // Find opponent's stats and rank
            if let Some(pos) = all_team_reb_stats.iter().position(|t| t.team_id == params.opponent_id) {
                let opp_stats = &all_team_reb_stats[pos];
                response.rebounds_allowed = Some(opp_stats.reb_allowed);
                response.oreb_allowed = Some(opp_stats.oreb_allowed);
                response.dreb_allowed = Some(opp_stats.dreb_allowed);

                // Calculate ranks (1 = allows fewest rebounds = best defense)
                // Sort by each stat to get individual ranks
                let mut reb_sorted: Vec<_> = all_team_reb_stats.iter().collect();
                reb_sorted.sort_by(|a, b| a.reb_allowed.partial_cmp(&b.reb_allowed).unwrap_or(std::cmp::Ordering::Equal));
                let reb_rank = reb_sorted.iter().position(|t| t.team_id == params.opponent_id).map(|p| (p + 1) as i32);

                let mut oreb_sorted: Vec<_> = all_team_reb_stats.iter().collect();
                oreb_sorted.sort_by(|a, b| a.oreb_allowed.partial_cmp(&b.oreb_allowed).unwrap_or(std::cmp::Ordering::Equal));
                let oreb_rank = oreb_sorted.iter().position(|t| t.team_id == params.opponent_id).map(|p| (p + 1) as i32);

                let mut dreb_sorted: Vec<_> = all_team_reb_stats.iter().collect();
                dreb_sorted.sort_by(|a, b| a.dreb_allowed.partial_cmp(&b.dreb_allowed).unwrap_or(std::cmp::Ordering::Equal));
                let dreb_rank = dreb_sorted.iter().position(|t| t.team_id == params.opponent_id).map(|p| (p + 1) as i32);

                // Store ranks in the zone name fields (repurposing for rebounds)
                response.dsz_name = Some("Total Reb".to_string());
                response.dsz_rank = reb_rank;
                response.dsz2_name = Some("OREB".to_string());
                response.dsz2_rank = oreb_rank;
                response.dpt_name = Some("DREB".to_string());
                response.dpt_rank = dreb_rank;
            }
        },
        _ => {}
    }

    Ok(Json(response))
}
