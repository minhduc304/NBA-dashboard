/**
 * API client for NBA Stats API
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8080';

// Types matching the Rust API responses
export interface ApiPlayer {
  playerId: number;
  player_name: string;
  season: string;
  points: number;
  assists: number;
  rebounds: number;
  threes_made: number;
  threes_attempted: number;
  fg_attempted: number;
  steals: number;
  blocks: number;
  turnovers: number;
  fouls: number;
  ft_attempted: number;
  pts_plus_ast: number;
  pts_plus_reb: number;
  ast_plus_reb: number;
  pts_plus_ast_plus_reb: number;
  steals_plus_blocks: number;
  double_doubles: number;
  triple_doubles: number;
  q1_points: number | null;
  q1_assists: number | null;
  q1_rebounds: number | null;
  first_half_points: number | null;
  games_played: number;
  last_updated: string;
}

export interface ApiScheduleGame {
  gameId: string;
  gameDate: string;
  gameTime: string;
  gameStatus: string;
  homeTeam: {
    id: number;
    name: string;
    abbreviation: string;
    city: string;
  };
  awayTeam: {
    id: number;
    name: string;
    abbreviation: string;
    city: string;
  };
}

export interface ApiScheduleResponse {
  games: ApiScheduleGame[];
  count: number;
}

// Roster types for tomorrow's games endpoint
export interface ApiRosterPlayer {
  playerId: number;
  playerName: string;
  position: string;
  injuryStatus: string;
  injuryDescription: string | null;
  hasProps: boolean;
}

export interface ApiGameWithRosters {
  gameId: string;
  gameDate: string;
  gameTime: string;
  gameStatus: string;
  homeTeam: {
    id: number;
    name: string;
    abbreviation: string;
    city: string;
  };
  awayTeam: {
    id: number;
    name: string;
    abbreviation: string;
    city: string;
  };
  homePlayers: ApiRosterPlayer[];
  awayPlayers: ApiRosterPlayer[];
}

export interface ApiRosterResponse {
  games: ApiGameWithRosters[];
  count: number;
}

export interface DnpPlayer {
  playerId: number;
  playerName: string;
  position: string | null;
  seasonAvg: number;
}

export interface ApiGameLog {
  gameId: string;
  playerId: string;
  teamId: number;
  season: string;
  gameDate: string;
  matchup: string;
  wl: string;
  min: number | null;
  pts: number | null;
  reb: number | null;
  ast: number | null;
  stl: number | null;
  blk: number | null;
  fgm: number | null;
  fga: number | null;
  fg3m: number | null;
  fg3a: number | null;
  ftm: number | null;
  fta: number | null;
  tov: number | null;
  gameMargin: number;
  oreb: number | null;
  dreb: number | null;
  dnpPlayers: DnpPlayer[];
}

// Prop line for a single stat
export interface ApiPropLine {
  statName: string;
  line: number;
  overOdds: number | null;
  underOdds: number | null;
  opponent: string | null;
  scheduledAt: string | null;
}

// Player props response
export interface ApiPlayerPropsResponse {
  playerName: string;
  opponentId: number;
  opponentName: string;
  props: ApiPropLine[];
}

// Play type matchup
export interface ApiPlayTypeMatchup {
  playType: string;
  playerPpg: number;
  pctOfTotal: number;
  oppPpp: number;
  oppRank: number;
}

export interface ApiPlayTypeMatchupResponse {
  playerName: string;
  opponentName: string;
  matchups: ApiPlayTypeMatchup[];
}

// Player shooting zone data
export interface ApiPlayerShootingZone {
  player_id: number;
  season: string;
  zone_name: string;
  fgm: number;
  fga: number;
  fg_pct: number;
  efg_pct: number;
  last_updated: string;
}

// Team defensive zone data
export interface ApiTeamDefensiveZone {
  team_id: number;
  season: string;
  zone_name: string;
  opp_fgm: number;
  opp_fga: number;
  opp_fg_pct: number;
  opp_efg_pct: number;
  last_updated: string;
}

// Shooting zone matchup with league context
export interface ApiShootingZoneMatchup {
  zoneName: string;
  playerFgm: number;
  playerFga: number;
  playerFgPct: number;       // Player's FG% (as percentage, e.g., 38.5)
  playerVolumePct: number;   // % of player's total FGA from this zone
  oppFgPct: number;          // Opponent allows (as percentage)
  oppRank: number;           // Opponent rank 1-30 (1 = best defense)
  leagueAvgPct: number;      // League average FG% for this zone
  advantage: number;         // League-adjusted advantage
  isThree: boolean;          // Is this a 3-point zone
  hasData: boolean;
}

export interface ApiShootingZoneMatchupResponse {
  playerName: string;
  playerId: number;
  opponentName: string;
  opponentId: number;
  totalFga: number;
  zones: ApiShootingZoneMatchup[];
}

/**
 * Fetch all players from the API
 */
export async function fetchPlayers(limit?: number, offset?: number): Promise<ApiPlayer[]> {
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());
  if (offset) params.append('offset', offset.toString());

  const url = `${API_BASE_URL}/api/players${params.toString() ? '?' + params.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch players: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch a single player by ID
 */
export async function fetchPlayerById(playerId: number): Promise<ApiPlayer> {
  const response = await fetch(`${API_BASE_URL}/api/players/${playerId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch player: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Search for a player by name
 */
export async function searchPlayer(name: string): Promise<ApiPlayer> {
  const response = await fetch(`${API_BASE_URL}/api/players/search?name=${encodeURIComponent(name)}`);
  if (!response.ok) {
    throw new Error(`Failed to search player: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch today's schedule
 */
export async function fetchTodaysSchedule(): Promise<ApiScheduleResponse> {
  const response = await fetch(`${API_BASE_URL}/api/schedule/today`);
  if (!response.ok) {
    throw new Error(`Failed to fetch schedule: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch schedule for a specific date
 */
export async function fetchScheduleByDate(date: string): Promise<ApiScheduleResponse> {
  const response = await fetch(`${API_BASE_URL}/api/schedule?date=${date}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch schedule: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch schedule for a specific team
 */
export async function fetchScheduleByTeam(teamAbbreviation: string): Promise<ApiScheduleResponse> {
  const response = await fetch(`${API_BASE_URL}/api/schedule?team=${teamAbbreviation}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch schedule: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch upcoming games (today + tomorrow) with player rosters
 * Games that have already started are filtered out on the backend
 */
export async function fetchUpcomingRosters(): Promise<ApiRosterResponse> {
  const response = await fetch(`${API_BASE_URL}/api/schedule/upcoming/rosters`);
  if (!response.ok) {
    throw new Error(`Failed to fetch upcoming rosters: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch game logs for a player with DNP information
 * @param playerId - Player ID to fetch logs for
 * @param limit - Number of games to fetch
 * @param statCategory - Stat category for DNP players (e.g., 'points', 'assists', 'rebounds')
 */
export async function fetchPlayerGameLogs(
  playerId: number,
  limit?: number,
  statCategory?: string
): Promise<ApiGameLog[]> {
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());
  if (statCategory) params.append('stat_category', statCategory);
  const url = `${API_BASE_URL}/api/players/${playerId}/game-logs${params.toString() ? '?' + params.toString() : ''}`

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch game logs: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch underdog props for a player
 */
export async function fetchPlayerProps(playerId: number): Promise<ApiPlayerPropsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/players/${playerId}/props`);
  if (!response.ok) {
    throw new Error(`Failed to fetch player props: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch play type matchup analysis for a player vs opponent
 */
export async function fetchPlayTypeMatchup(playerId: number, opponentId: number): Promise<ApiPlayTypeMatchupResponse> {
  const response = await fetch(`${API_BASE_URL}/api/players/${playerId}/play-type-matchup?opponent_id=${opponentId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch play type matchup: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch player shooting zones (FG% by court zone)
 */
export async function fetchPlayerShootingZones(playerId: number): Promise<ApiPlayerShootingZone[]> {
  const response = await fetch(`${API_BASE_URL}/api/players/${playerId}/shooting-zones`);
  if (!response.ok) {
    if (response.status === 404) {
      return []; // No shooting zone data for this player
    }
    throw new Error(`Failed to fetch shooting zones: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch team defensive zones (opponent FG% allowed by zone)
 */
export async function fetchTeamDefensiveZones(teamId: number): Promise<ApiTeamDefensiveZone[]> {
  const response = await fetch(`${API_BASE_URL}/api/teams/${teamId}/defensive-zones`);
  if (!response.ok) {
    if (response.status === 404) {
      return []; // No defensive zone data for this team
    }
    throw new Error(`Failed to fetch defensive zones: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch shooting zone matchup with league context (league avg, opponent rank, volume)
 */
export async function fetchShootingZoneMatchup(
  playerId: number,
  opponentId: number
): Promise<ApiShootingZoneMatchupResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/players/${playerId}/shooting-zones/vs/${opponentId}`
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch shooting zone matchup: ${response.statusText}`);
  }
  return response.json();
}

// Assist Zone Matchup types
export interface ApiAssistZoneMatchup {
  zoneName: string;
  playerAssists: number;
  playerAstPct: number;
  oppDefRank: number;
  oppDefFgPct: number;
  hasData: boolean;
}

export interface ApiAssistZoneMatchupResponse {
  playerName: string;
  opponentName: string;
  totalAssists: number;
  zones: ApiAssistZoneMatchup[];
}

export async function fetchAssistZoneMatchup(
  playerId: number,
  opponentId: number
): Promise<ApiAssistZoneMatchupResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/players/${playerId}/assist-zone-matchup?opponent_id=${opponentId}`
  );

  if (!response.ok) {
    if (response.status === 404) {
      return {
        playerName: '',
        opponentName: '',
        totalAssists: 0,
        zones: []
      };
    }
    throw new Error(`Failed to fetch assist zone matchup: ${response.statusText}`);
  }

  return response.json();
}

// ── Top Picks (Underdog vs Sharp Books) ──

export interface ApiSharpBookLine {
  sportsbook: string;
  line: number;
  overOdds: number | null;
  underOdds: number | null;
}

export interface ApiTopPick {
  playerName: string;
  statType: string;
  direction: string;
  udLine: number;
  udOdds: number | null;
  udImpliedProb: number;
  edgePct: number;
  bestBook: string;
  bestBookDeviggedProb: number;
  books: ApiSharpBookLine[];
  homeTeam: string;
  awayTeam: string;
  gameDate: string;
}

export interface ApiTopPicksResponse {
  picks: ApiTopPick[];
  lastUpdated: string | null;
}

/**
 * Fetch top +EV picks (DFS lines vs sharp consensus)
 */
export async function fetchTopPicks(
  gameDate?: string,
): Promise<ApiTopPicksResponse> {
  const params = new URLSearchParams();
  if (gameDate) params.append('game_date', gameDate);
  const qs = params.toString();
  const url = `${API_BASE_URL}/api/screener/top-picks${qs ? '?' + qs : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch top picks: ${response.statusText}`);
  }

  return response.json();
}

// Upcoming matchup context for tooltip
export interface ApiUpcomingMatchupContext {
  opponentName: string;
  statType: 'points' | 'assists' | 'rebounds';
  defRtg: number | null;
  pace: number | null;
  // Points-specific (dominant shooting zones)
  dszRank: number | null;
  dszName: string | null;
  dsz2Rank: number | null;
  dsz2Name: string | null;
  // Points-specific (dominant play types)
  dptRank: number | null;
  dptName: string | null;
  dpt2Rank: number | null;
  dpt2Name: string | null;
  // Assists-specific (dominant assist zones)
  dazRank: number | null;
  dazName: string | null;
  daz2Rank: number | null;
  daz2Name: string | null;
  assistsAllowed: number | null;
  // Rebounds-specific
  reboundsAllowed: number | null;
  orebAllowed: number | null;
  drebAllowed: number | null;
}

/**
 * Fetch upcoming matchup defensive context for tooltip
 * @param playerId - Player ID
 * @param opponentId - Opponent team ID
 * @param statType - "points", "assists", or "rebounds"
 */
export async function fetchUpcomingMatchupContext(
  playerId: number,
  opponentId: number,
  statType: string
): Promise<ApiUpcomingMatchupContext> {
  const response = await fetch(
    `${API_BASE_URL}/api/players/${playerId}/upcoming-matchup?opponent_id=${opponentId}&stat_type=${statType}`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch upcoming matchup context: ${response.statusText}`);
  }

  return response.json();
}

