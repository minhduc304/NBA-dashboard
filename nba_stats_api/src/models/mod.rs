use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize, sqlx::FromRow)]
pub struct PlayerStats {
    pub player_id: i64,
    pub player_name: String,
    pub season: String,
    pub points: f32,
    pub assists: f32,
    pub rebounds: f32,
    pub threes_made: f32,
    pub steals: f32,
    pub blocks: f32,
    pub turnovers: f32,
    pub fouls: f32,
    pub ft_attempted: f32,
    pub pts_plus_ast: f32,
    pub pts_plus_reb: f32,
    pub ast_plus_reb: f32,
    pub pts_plus_ast_plus_reb: f32,
    pub steals_plus_blocks: f32,
    pub double_doubles: i64,
    pub triple_doubles: i64,
    pub q1_points: Option<f32>,
    pub q1_assists: Option<f32>,
    pub q1_rebounds: Option<f32>,
    pub first_half_points: Option<f32>,
    pub games_played: i64,
    pub last_updated: String
}

#[derive(Serialize, Deserialize, sqlx::FromRow)]
pub struct PlayerShootingZones {
    pub player_id: i64,
    pub season: String,
    pub zone_name: String,
    pub fgm: f32,
    pub fga: f32,
    pub fg_pct: f32,
    pub efg_pct: f32,
    pub last_updated: String
}

#[derive(Serialize, Deserialize, sqlx::FromRow)]
pub struct PlayerAssistZones {
    pub player_id: i64,
    pub season: String,
    pub zone_name: String,
    pub assists: i64,
    pub ast_fgm: i64,
    pub ast_fga: i64,
    pub last_game_id: String,
    pub last_game_date: String,
    pub games_analyzed: i64,
    pub last_updated: String
}

#[derive(Serialize, Deserialize, sqlx::FromRow)]
pub struct PlayerPlayTypes {
    pub player_id: i64,
    pub season: String,
    pub play_type: String,
    pub points: f32,
    pub points_per_game: f32,
    pub possessions: f32,
    pub poss_per_game: f32,
    pub ppp: f32,
    pub fg_pct: f32,
    pub pct_of_total_points: f32,
    pub games_played: i64,
    pub last_updated: String
}

#[derive(Serialize, Deserialize, sqlx::FromRow)]
pub struct TeamDefensiveZones {
    pub team_id: i64,
    pub season: String,
    pub zone_name: String,
    pub opp_fgm: f32,
    pub opp_fga: f32,
    pub opp_fg_pct: f32,
    pub opp_efg_pct: f32,
    pub last_updated: String
}

#[derive(Serialize, Deserialize, sqlx::FromRow)]
pub struct TeamDefensivePlayTypes {
    pub team_id: i64,
    pub season: String,
    pub play_type: String,
    pub poss_pct: f32,
    pub possessions: f32,
    pub poss_per_game: f32,
    pub ppp: f32,
    pub fg_pct: f32,
    pub efg_pct: f32,
    pub points: f32,
    pub points_per_game: f32,
    pub games_played: i64,
    pub last_updated: String,
}

