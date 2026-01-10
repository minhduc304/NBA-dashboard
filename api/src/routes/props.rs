use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
};
use sqlx::sqlite::SqlitePool;
use std::collections::HashMap;
use crate::models::{PlayerPropsResponse, PropLine};
use crate::db;

/// GET /api/players/:id/props - Get underdog props for a player
pub async fn get_player_props(
    State(pool): State<SqlitePool>,
    Path(player_id): Path<i64>,
) -> Result<Json<PlayerPropsResponse>, StatusCode> {
    // Get raw props from database
    let props = db::get_player_props_by_id(&pool, player_id)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if props.is_empty() {
        // Return empty response with player name if we can get it
        let player = db::get_player_by_id(&pool, player_id)
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        return Ok(Json(PlayerPropsResponse {
            player_name: player.map(|p| p.player_name).unwrap_or_default(),
            opponent_id: None,
            opponent_name: None,
            props: vec![],
        }));
    }

    // Group props by stat_name and combine over/under
    let mut grouped: HashMap<String, PropLine> = HashMap::new();
    let player_name = props.first().map(|p| p.full_name.clone()).unwrap_or_default();
    let opponent_name = props.first().and_then(|p| p.opponent_name.clone());
    let scheduled_at = props.first().and_then(|p| p.scheduled_at.clone());

    // Look up opponent team ID from name
    let opponent_id = if let Some(ref opp_name) = opponent_name {
        // Get all teams and find the matching one
        let teams = db::get_all_teams(&pool)
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        teams.iter().find(|t| &t.full_name == opp_name).map(|t| t.team_id)
    } else {
        None
    };

    for prop in props {
        let entry = grouped.entry(prop.stat_name.clone()).or_insert(PropLine {
            stat_name: prop.stat_name.clone(),
            line: prop.stat_value,
            over_odds: None,
            under_odds: None,
            opponent: opponent_name.clone(),
            scheduled_at: scheduled_at.clone(),
        });

        match prop.choice.as_str() {
            "over" => entry.over_odds = prop.american_price,
            "under" => entry.under_odds = prop.american_price,
            _ => {}
        }
    }

    // Convert to vec and sort by stat importance
    let stat_order = [
        "points", "rebounds", "assists", "pts_rebs_asts", "pts_asts",
        "pts_rebs", "rebs_asts", "three_points_made", "blks_stls",
        "steals", "blocks", "turnovers", "free_throws_made",
    ];

    let mut prop_lines: Vec<PropLine> = grouped.into_values().collect();
    prop_lines.sort_by(|a, b| {
        let a_idx = stat_order.iter().position(|&s| s == a.stat_name).unwrap_or(99);
        let b_idx = stat_order.iter().position(|&s| s == b.stat_name).unwrap_or(99);
        a_idx.cmp(&b_idx)
    });

    Ok(Json(PlayerPropsResponse {
        player_name,
        opponent_id,
        opponent_name,
        props: prop_lines,
    }))
}
