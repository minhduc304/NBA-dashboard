use serde::{Serialize, Deserialize};

/// Player roster info for sidebar display
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct RosterPlayer {
    pub player_id: i64,
    pub player_name: String,
    pub position: Option<String>,
    pub injury_status: String,
    pub injury_description: Option<String>,
    pub has_props: bool,
}

/// Row from database for roster players
#[derive(Debug, sqlx::FromRow)]
pub struct RosterPlayerRow {
    pub player_id: i64,
    pub player_name: String,
    pub position: Option<String>,
    pub injury_status: Option<String>,
    pub injury_description: Option<String>,
    pub has_props: bool,
}

impl RosterPlayerRow {
    pub fn to_roster_player(&self) -> RosterPlayer {
        RosterPlayer {
            player_id: self.player_id,
            player_name: self.player_name.clone(),
            position: self.position.clone(),
            injury_status: self.injury_status.clone().unwrap_or_else(|| "Available".to_string()),
            injury_description: self.injury_description.clone(),
            has_props: self.has_props,
        }
    }
}

/// Game with player rosters for sidebar
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GameWithRosters {
    pub game_id: String,
    pub game_date: String,
    pub game_time: String,
    pub game_status: String,
    pub home_team: TeamInfo,
    pub away_team: TeamInfo,
    pub home_players: Vec<RosterPlayer>,
    pub away_players: Vec<RosterPlayer>,
}

/// Response wrapper for roster endpoint
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RosterResponse {
    pub games: Vec<GameWithRosters>,
    pub count: usize,
}

/// Team info from teams table
#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct Team {
    pub team_id: i64,
    pub name: String,
    pub full_name: String,
    pub abbreviation: String,
    pub city: String,
    pub state: Option<String>,
    pub year_founded: Option<i64>,
    pub last_updated: Option<String>,
}


/// Game info for API responses
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ScheduleGame {
    pub game_id: String,
    pub game_date: String,
    pub game_time: String,
    pub game_status: String,
    pub home_team: TeamInfo,
    pub away_team: TeamInfo,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TeamInfo {
    pub id: i64,
    pub name: String,
    pub abbreviation: String,
    pub city: String,
}

/// Response wrapper for schedule endpoint
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ScheduleResponse {
    pub games: Vec<ScheduleGame>,
    pub count: usize,
}

/// Schedule row from SQLite database
#[derive(Debug, sqlx::FromRow)]
pub struct ScheduleRow {
    pub game_id: String,
    pub game_date: String,
    pub game_time: Option<String>,
    pub game_status: Option<String>,
    pub home_team_id: i64,
    pub home_team_name: Option<String>,
    pub home_team_abbreviation: Option<String>,
    pub home_team_city: Option<String>,
    pub away_team_id: i64,
    pub away_team_name: Option<String>,
    pub away_team_abbreviation: Option<String>,
    pub away_team_city: Option<String>,
    // pub last_updated: Option<String>,
}

impl ScheduleRow {
    /// Convert database row to API response format
    pub fn to_schedule_game(&self) -> ScheduleGame {
        ScheduleGame {
            game_id: self.game_id.clone(),
            game_date: self.game_date.clone(),
            game_time: self.game_time.clone().unwrap_or_else(|| "TBD".to_string()),
            game_status: self.game_status.clone().unwrap_or_default(),
            home_team: TeamInfo {
                id: self.home_team_id,
                name: self.home_team_name.clone().unwrap_or_default(),
                abbreviation: self.home_team_abbreviation.clone().unwrap_or_default(),
                city: self.home_team_city.clone().unwrap_or_default(),
            },
            away_team: TeamInfo {
                id: self.away_team_id,
                name: self.away_team_name.clone().unwrap_or_default(),
                abbreviation: self.away_team_abbreviation.clone().unwrap_or_default(),
                city: self.away_team_city.clone().unwrap_or_default(),
            },
        }
    }
}

#[derive(Serialize, Deserialize, sqlx::FromRow)]
pub struct PlayerStats {
    pub player_id: i64,
    pub player_name: String,
    pub season: String,
    pub team_id: Option<i64>,
    pub points: f32,
    pub assists: f32,
    pub rebounds: f32,
    pub threes_made: f32,
    pub threes_attempted: Option<f32>,
    pub fg_attempted: Option<f32>,
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
    #[sqlx(rename = "ast")]
    pub assists: i64,
    #[sqlx(rename = "fgm")]
    pub ast_fgm: i64,
    #[sqlx(rename = "fga")]
    pub ast_fga: i64,
    pub last_updated: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AssistZoneMatchup {
    pub zone_name: String,
    pub player_assists: i64,
    pub player_ast_pct: f32,
    pub opp_def_rank: i32,
    pub opp_def_fg_pct: f32,
    pub has_data: bool,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AssistZoneMatchupResponse {
    pub player_name: String,
    pub opponent_name: String,
    pub total_assists: i64,
    pub zones: Vec<AssistZoneMatchup>,
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

// Shooting zone matchup with league context
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ShootingZoneMatchup {
    pub zone_name: String,
    pub player_fgm: f32,
    pub player_fga: f32,
    pub player_fg_pct: f32,       // Player's FG% (already as percentage, e.g., 38.5)
    pub player_volume_pct: f32,   // % of player's total FGA from this zone
    pub opp_fg_pct: f32,          // Opponent allows (as percentage)
    pub opp_rank: i32,            // Opponent rank 1-30 (1 = best defense)
    pub league_avg_pct: f32,      // League average FG% for this zone
    pub advantage: f32,           // League-adjusted advantage
    pub is_three: bool,           // Is this a 3-point zone
    pub has_data: bool,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ShootingZoneMatchupResponse {
    pub player_name: String,
    pub player_id: i64,
    pub opponent_name: String,
    pub opponent_id: i64,
    pub total_fga: f32,
    pub zones: Vec<ShootingZoneMatchup>,
}

//
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

// DNP (Did Not Play) player info
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DnpPlayer {
    pub player_id: i64,
    pub player_name: String,
    pub position: Option<String>,
    pub season_avg: f32,  // Season average for the relevant stat
}

// Player game log for individual game stats
#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct PlayerGameLog {
    pub game_id: String,
    pub player_id: String,
    pub team_id: Option<i64>,
    pub season: Option<String>,
    pub game_date: Option<String>,
    pub matchup: Option<String>,
    pub wl: Option<String>,
    pub min: Option<f32>,
    pub pts: Option<i32>,
    pub reb: Option<i32>,
    pub ast: Option<i32>,
    pub stl: Option<i32>,
    pub blk: Option<i32>,
    pub fgm: Option<i32>,
    pub fga: Option<i32>,
    pub fg3m: Option<i32>,
    pub fg3a: Option<i32>,
    pub ftm: Option<i32>,
    pub fta: Option<i32>,
    pub tov: Option<i32>,
    pub game_margin: Option<i32>,
    pub oreb: Option<i32>,
    pub dreb: Option<i32>,
}

// Game log with DNP players included
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GameLogWithDnp {
    #[serde(flatten)]
    pub game_log: PlayerGameLog,
    pub dnp_players: Vec<DnpPlayer>,
}

// Underdog prop line from database
#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct UnderdogProp {
    pub id: i64,
    pub full_name: String,
    pub team_name: Option<String>,
    pub opponent_name: Option<String>,
    pub stat_name: String,
    pub stat_value: f64,
    pub choice: String,
    pub american_price: Option<i64>,
    pub decimal_price: Option<f64>,
    pub scheduled_at: Option<String>,
}

// Response for player props endpoint
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlayerPropsResponse {
    pub player_name: String,
    pub opponent_id: Option<i64>,
    pub opponent_name: Option<String>,
    pub props: Vec<PropLine>,
}

// Grouped prop line (over/under combined)
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PropLine {
    pub stat_name: String,
    pub line: f64,
    pub over_odds: Option<i64>,
    pub under_odds: Option<i64>,
    pub opponent: Option<String>,
    pub scheduled_at: Option<String>,
}

// Play type matchup analysis
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlayTypeMatchup {
    pub play_type: String,
    pub player_ppg: f32,
    pub pct_of_total: f32,
    pub opp_ppp: f32,
    pub opp_rank: i32,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlayTypeMatchupResponse {
    pub player_name: String,
    pub opponent_name: String,
    pub matchups: Vec<PlayTypeMatchup>,
}

// ── Top Picks (Underdog vs Sharp Books) ──

/// Raw row: one per sharp-book × Underdog line match
#[derive(Debug, sqlx::FromRow)]
pub struct TopPickRow {
    pub player_name: String,
    pub stat_type: String,
    pub ud_line: f64,
    pub ud_odds: Option<i32>,
    pub sportsbook: String,
    pub book_line: f64,
    pub over_odds: Option<i32>,
    pub under_odds: Option<i32>,
    pub home_team: String,
    pub away_team: String,
    pub game_date: String,
    pub game_time: Option<String>,
}

/// One sharp book's line + odds for the expanded view
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct SharpBookLine {
    pub sportsbook: String,
    pub line: f64,
    pub over_odds: Option<i32>,
    pub under_odds: Option<i32>,
}

/// Computed top pick for the API response
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TopPick {
    pub player_name: String,
    pub stat_type: String,
    pub direction: String,
    pub ud_line: f64,
    pub ud_odds: Option<i32>,
    pub ud_implied_prob: f64,
    pub edge_pct: f64,
    pub best_book: String,
    pub best_book_devigged_prob: f64,
    pub books: Vec<SharpBookLine>,
    pub home_team: String,
    pub away_team: String,
    pub game_date: String,
}

/// Top-level response for /api/screener/top-picks
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TopPicksResponse {
    pub picks: Vec<TopPick>,
    pub last_updated: Option<String>,
}

/// Team pace and rating stats
#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
#[serde(rename_all = "camelCase")]
pub struct TeamStats {
    pub team_id: i64,
    pub season: String,
    pub pace: Option<f32>,
    pub off_rating: Option<f32>,
    pub def_rating: Option<f32>,
    pub net_rating: Option<f32>,
    pub games_played: Option<i64>,
    pub wins: Option<i64>,
    pub losses: Option<i64>,
}

/// Upcoming matchup defensive context response
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpcomingMatchupResponse {
    pub opponent_name: String,
    pub stat_type: String,
    // Team stats
    pub def_rtg: Option<f32>,
    pub pace: Option<f32>,
    // Points-specific (dominant shooting zone ranks)
    pub dsz_rank: Option<i32>,
    pub dsz_name: Option<String>,
    pub dsz2_rank: Option<i32>,
    pub dsz2_name: Option<String>,
    // Points-specific (dominant play type ranks)
    pub dpt_rank: Option<i32>,
    pub dpt_name: Option<String>,
    pub dpt2_rank: Option<i32>,
    pub dpt2_name: Option<String>,
    // Assists-specific (dominant assist zone ranks)
    pub daz_rank: Option<i32>,
    pub daz_name: Option<String>,
    pub daz2_rank: Option<i32>,
    pub daz2_name: Option<String>,
    pub assists_allowed: Option<f32>,
    // Rebounds-specific
    pub rebounds_allowed: Option<f32>,
    pub oreb_allowed: Option<f32>,
    pub dreb_allowed: Option<f32>,
}

