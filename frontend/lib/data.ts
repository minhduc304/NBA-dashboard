import { fetchPlayers, type ApiPlayer, type ApiGameLog } from './api';

// NBA Team data with all 30 teams (primary and secondary colors)
export const NBA_TEAMS: Record<string, { name: string; short: string; color: string; colorSecondary: string }> = {
  ATL: { name: 'Hawks', short: 'ATL', color: '#E03A3E', colorSecondary: '#C1D32F' },
  BOS: { name: 'Celtics', short: 'BOS', color: '#007A33', colorSecondary: '#BA9653' },
  BKN: { name: 'Nets', short: 'BKN', color: '#000000', colorSecondary: '#FFFFFF' },
  CHA: { name: 'Hornets', short: 'CHA', color: '#1D1160', colorSecondary: '#00788C' },
  CHI: { name: 'Bulls', short: 'CHI', color: '#CE1141', colorSecondary: '#000000' },
  CLE: { name: 'Cavaliers', short: 'CLE', color: '#860038', colorSecondary: '#FDBB30' },
  DAL: { name: 'Mavericks', short: 'DAL', color: '#00538C', colorSecondary: '#002B5E' },
  DEN: { name: 'Nuggets', short: 'DEN', color: '#0E2240', colorSecondary: '#FEC524' },
  DET: { name: 'Pistons', short: 'DET', color: '#C8102E', colorSecondary: '#1D42BA' },
  GSW: { name: 'Warriors', short: 'GSW', color: '#1D428A', colorSecondary: '#FFC72C' },
  HOU: { name: 'Rockets', short: 'HOU', color: '#CE1141', colorSecondary: '#000000' },
  IND: { name: 'Pacers', short: 'IND', color: '#002D62', colorSecondary: '#FDBB30' },
  LAC: { name: 'Clippers', short: 'LAC', color: '#C8102E', colorSecondary: '#1D428A' },
  LAL: { name: 'Lakers', short: 'LAL', color: '#552583', colorSecondary: '#FDB927' },
  MEM: { name: 'Grizzlies', short: 'MEM', color: '#5D76A9', colorSecondary: '#12173F' },
  MIA: { name: 'Heat', short: 'MIA', color: '#98002E', colorSecondary: '#F9A01B' },
  MIL: { name: 'Bucks', short: 'MIL', color: '#00471B', colorSecondary: '#EEE1C6' },
  MIN: { name: 'Timberwolves', short: 'MIN', color: '#0C2340', colorSecondary: '#236192' },
  NOP: { name: 'Pelicans', short: 'NOP', color: '#0C2340', colorSecondary: '#C8102E' },
  NYK: { name: 'Knicks', short: 'NYK', color: '#006BB6', colorSecondary: '#F58426' },
  OKC: { name: 'Thunder', short: 'OKC', color: '#007AC1', colorSecondary: '#EF3B24' },
  ORL: { name: 'Magic', short: 'ORL', color: '#0077C0', colorSecondary: '#C4CED4' },
  PHI: { name: '76ers', short: 'PHI', color: '#006BB6', colorSecondary: '#ED174C' },
  PHX: { name: 'Suns', short: 'PHX', color: '#1D1160', colorSecondary: '#E56020' },
  POR: { name: 'Trail Blazers', short: 'POR', color: '#E03A3E', colorSecondary: '#000000' },
  SAC: { name: 'Kings', short: 'SAC', color: '#5A2D81', colorSecondary: '#63727A' },
  SAS: { name: 'Spurs', short: 'SAS', color: '#C4CED4', colorSecondary: '#000000' },
  TOR: { name: 'Raptors', short: 'TOR', color: '#CE1141', colorSecondary: '#000000' },
  UTA: { name: 'Jazz', short: 'UTA', color: '#002B5C', colorSecondary: '#00471B' },
  WAS: { name: 'Wizards', short: 'WAS', color: '#002B5C', colorSecondary: '#E31837' },
} as const;

export type TeamKey = keyof typeof NBA_TEAMS;

// Player data interface
export interface Player {
  id: string;
  name: string;
  position: string;
  team: string;
  avatar?: string;
  isLocked?: boolean;
  line?: number;
  overOdds?: number;
  underOdds?: number;
  badges?: string[];
  // Stats from API
  points?: number;
  assists?: number;
  rebounds?: number;
  gamesPlayed?: number;
  // Opponent info from game schedule
  opponentId?: number;
  opponentName?: string;
  opponentAbbr?: string;
}

// Game matchup interface
export interface GameMatchup {
  id: string;
  homeTeam: string;
  awayTeam: string;
  time: string;
  date: string;
}

// Chart data point interface
export interface ChartDataPoint {
  date: string;
  opponent: string;
  value: number | null;
  isOver: boolean;
  isFuture?: boolean;
  // Game context
  wl: string | null;
  gameMargin: number | null;
  min: number | null;
  // Scoring breakdown
  fgm: number | null;
  fga: number | null;
  fg3m: number | null;
  fg3a: number | null;
  ftm: number | null;
  fta: number | null;
}

// Player stats interface for display
export interface PlayerStats {
  seasonAvg: number;
  graphAvg: number;
  hitRate: number;
  hitRateFraction: string;
  line: number;
  overOdds: number;
  underOdds: number;
}

// Stat categories
export const STAT_CATEGORIES = [
  'Points',
  'Assists',
  'Rebounds',
  '3PM',
  '3PA',
  'FGA',
  'Pts+Ast',
  'Pts+Reb',
  'Ast+Reb',
  'PRA',
  'Steals',
  'Blocks',
  'Stl+Blk',
  'Turnovers',
] as const;

export type StatCategory = typeof STAT_CATEGORIES[number];

// Map stat categories to game log fields (for chart data)
export const STAT_TO_FIELD: Record<StatCategory, string | string[]> = {
  'Points': 'pts',
  'Assists': 'ast',
  'Rebounds': 'reb',
  '3PM': 'fg3m',
  '3PA': 'fg3a',
  'FGA': 'fga',
  'Pts+Ast': ['pts', 'ast'],        // Combo stats need multiple fields
  'Pts+Reb': ['pts', 'reb'],
  'Ast+Reb': ['ast', 'reb'],
  'PRA': ['pts', 'reb', 'ast'],     // Points + Rebounds + Assists
  'Steals': 'stl',
  'Blocks': 'blk',
  'Stl+Blk': ['stl', 'blk'],
  'Turnovers': 'tov',
}

// Map stat categories to ApiPlayer fields (for season averages)
// These match the field names from /api/players/{id} response
export const STAT_TO_API_FIELD: Record<StatCategory, keyof import('./api').ApiPlayer> = {
  'Points': 'points',
  'Assists': 'assists',
  'Rebounds': 'rebounds',
  '3PM': 'threes_made',
  '3PA': 'threes_attempted',
  'FGA': 'fg_attempted',
  'Pts+Ast': 'pts_plus_ast',
  'Pts+Reb': 'pts_plus_reb',
  'Ast+Reb': 'ast_plus_reb',
  'PRA': 'pts_plus_ast_plus_reb',
  'Steals': 'steals',
  'Blocks': 'blocks',
  'Stl+Blk': 'steals_plus_blocks',
  'Turnovers': 'turnovers',
}

// ============================================
// API Data Cache
// ============================================

let allPlayersCache: Player[] | null = null;

/**
 * Transform API player to frontend Player format
 */
function transformApiPlayer(apiPlayer: ApiPlayer): Player {
  return {
    id: apiPlayer.playerId.toString(),
    name: apiPlayer.player_name,
    position: 'G', // Default - no position data in API yet
    team: 'UNK',   // Default - no team data in API yet
    isLocked: false,
    // No sportsbook data available
    line: undefined,
    overOdds: undefined,
    underOdds: undefined,
    // Stats from API
    points: apiPlayer.points,
    assists: apiPlayer.assists,
    rebounds: apiPlayer.rebounds,
    gamesPlayed: apiPlayer.games_played,
  };
}

/**
 * Transform game logs to chart data format 
 */
export function transformGameLogsToChartData(
  gameLogs: ApiGameLog[],
  statCategory: StatCategory
): ChartDataPoint[] {
  const field = STAT_TO_FIELD[statCategory];

  return gameLogs
      .slice()  // Create a copy so we don't mutate original
      .reverse()  // API returns newest first, chart shows oldest first (left to right)
      .map((log) => {
        // Calculate the stat value
        let value: number | null = null;

        if (Array.isArray(field)) {
          // Combo stat: sum the fields
          const values = field.map(f => (log as unknown as Record<string, number | null>)[f] ?? 0);
          value = values.reduce((sum, v) => sum + (v ?? 0), 0);
        } else {
          // Single stat
          value = (log as unknown as Record<string, number | null>)[field] ?? null;
        }

        // Parse opponent from matchup (e.g., "NYK @ ORL" → "ORL")
        const opponent = parseOpponentFromMatchup(log.matchup);

        // Format date (e.g., "2025-12-13" → "Dec 13")
        const date = formatGameDate(log.gameDate);

        return {
          date,
          opponent,
          value,
          isOver: false,  // Will be calculated by chart based on line
          isFuture: false,
          // Game context
          wl: log.wl,
          gameMargin: log.gameMargin,
          min: log.min,
          // Scoring breakdown
          fgm: log.fgm,
          fga: log.fga,
          fg3m: log.fg3m,
          fg3a: log.fg3a,
          ftm: log.ftm,
          fta: log.fta,
        };
      });
}

/**
 * Extract opponent abbreviation from matchup string
 * e.g. "NYK @ ORL" (away game) -> "ORL"
 * e.g. "NYK vs. BOS" (home game) -> "BOS"
 */
function parseOpponentFromMatchup(matchup: string | null): string {
  if (!matchup) return 'UNK';

  // Away format
  if (matchup.includes('@')) {
    return matchup.split('@')[1]?.trim() || 'UNK';
  }

  // Home format
  if (matchup.includes('vs.')) {
    return matchup.split('vs.')[1]?.trim() || 'UNK';
  }

  return 'UNK';
}


/**
 * Format game date for chart display
 * e.g., "2025-12-13T00:00:00" → "Dec 13"
 */
function formatGameDate(dateStr: string | null): string {
  if (!dateStr) return '';

  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: '2-digit' });
  } catch {
    return '';
  }
}

/**
 * Fetch all players from API (cached)
 */
export async function loadAllPlayers(): Promise<Player[]> {
  if (allPlayersCache) return allPlayersCache;

  try {
    const apiPlayers = await fetchPlayers();
    allPlayersCache = apiPlayers.map(transformApiPlayer);
    return allPlayersCache;
  } catch (error) {
    console.error('Failed to load players from API:', error);
    return [];
  }
}

/**
 * Search players by name from API data
 */
export async function searchPlayersFromApi(query: string): Promise<Player[]> {
  const players = await loadAllPlayers();
  const lowerQuery = query.toLowerCase();

  return players
    .filter(p => p.name.toLowerCase().includes(lowerQuery))
    .slice(0, 10); // Limit results
}

/**
 * Get player stats for display
 * Shows ? for line/odds since we don't have sportsbook data
 */
export function getPlayerStats(player: Player): PlayerStats {
  const points = player.points || 20; // Fallback

  return {
    seasonAvg: Math.round(points * 10) / 10,
    graphAvg: Math.round(points * 10) / 10,
    hitRate: 0,
    hitRateFraction: '?/?',
    line: player.line || 0,
    overOdds: player.overOdds || 0,
    underOdds: player.underOdds || 0,
  };
}
