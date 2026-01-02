'use client';

import { useMemo, useState, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Minus, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { STAT_CATEGORIES, STAT_TO_API_FIELD, getPlayerStats, transformGameLogsToChartData, NBA_TEAMS, type Player, type StatCategory, type ChartDataPoint } from '@/lib/data';
import { fetchPlayerGameLogs, fetchPlayerById, fetchPlayerProps, fetchPlayTypeMatchup, type ApiGameLog, type ApiPlayer, type ApiPropLine, type ApiPlayTypeMatchup } from '@/lib/api';
import { StatsChart, type HitRateInfo } from './StatsChart';
import { ShootingZonesCard } from './ShootingZonesCard';
import { AssistZonesCard } from './AssistZonesCard';

const seasons = ['24/25', '25/26', 'All'];
const splits = ['H2H', 'Home', 'Away', 'More'];

// Format American odds for display
const formatOdds = (odds: number | null): string => {
  if (odds === null) return '—';
  return odds >= 0 ? `+${odds}` : `${odds}`;
};

// Map StatCategory to underdog prop stat names
const STAT_CATEGORY_TO_PROP: Record<string, string> = {
  'Points': 'points',
  'Assists': 'assists',
  'Rebounds': 'rebounds',
  '3PM': 'three_points_made',
  '3PA': 'three_points_att',
  'FGA': 'field_goals_att',
  'Pts+Ast': 'pts_asts',
  'Pts+Reb': 'pts_rebs',
  'Ast+Reb': 'rebs_asts',
  'PRA': 'pts_rebs_asts',
  'Steals': 'steals',
  'Blocks': 'blocks',
  'Stl+Blk': 'blks_stls',
  'Turnovers': 'turnovers',
  'Fantasy': 'fantasy_points',
  'Double': 'double_doubles',
};

interface MainContentProps {
  player: Player | null;
}

export function MainContent({ player }: MainContentProps) {
  const [activeStat, setActiveStat] = useState<StatCategory>('Points');
  const [activeSeason, setActiveSeason] = useState('25/26');
  const [gamesCount, setGamesCount] = useState(20);
  const [rankingsView, setRankingsView] = useState<'All' | 'L15'>('All');

  // Dynamic line value and hit rate from chart interaction
  const [currentLineValue, setCurrentLineValue] = useState<number | null>(null);
  const [currentHitRate, setCurrentHitRate] = useState<HitRateInfo | null>(null);

  // Game logs state
  const [gameLogs, setGameLogs] = useState<ApiGameLog[]>([]);
  const [isLoadingLogs, setIsLoadingLogs] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);

  // Player stats state (for season averages)
  const [playerStats, setPlayerStats] = useState<ApiPlayer | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  // Player props state (underdog lines)
  const [playerProps, setPlayerProps] = useState<ApiPropLine[]>([]);
  const [isLoadingProps, setIsLoadingProps] = useState(false);
  const [opponentId, setOpponentId] = useState<number | null>(null);
  const [opponentName, setOpponentName] = useState<string | null>(null);

  // Play type matchup state
  const [playTypeMatchups, setPlayTypeMatchups] = useState<ApiPlayTypeMatchup[]>([]);
  const [isLoadingMatchups, setIsLoadingMatchups] = useState(false);

  // Generate stats based on player - memoized to avoid recalculating on every render
  const stats = useMemo(() => {
    if (!player) return null;
    return getPlayerStats(player);
  }, [player?.id]); // Only recalculate when player changes

  // Fetch player stats (season averages) when player changes
  useEffect(() => {
    if (!player) {
      setPlayerStats(null);
      return;
    }

    const playerId = parseInt(player.id, 10);
    if (isNaN(playerId)) {
      setPlayerStats(null);
      return;
    }

    const loadPlayerStats = async () => {
      setIsLoadingStats(true);
      try {
        const stats = await fetchPlayerById(playerId);
        setPlayerStats(stats);
      } catch (err) {
        console.error('Failed to fetch player stats:', err);
        setPlayerStats(null);
      } finally {
        setIsLoadingStats(false);
      }
    };

    loadPlayerStats();
  }, [player?.id]);

  // Fetch player props when player changes
  useEffect(() => {
    if (!player) {
      setPlayerProps([]);
      setOpponentId(null);
      setOpponentName(null);
      return;
    }

    const playerId = parseInt(player.id, 10);
    if (isNaN(playerId)) {
      setPlayerProps([]);
      setOpponentId(null);
      setOpponentName(null);
      return;
    }

    // Set opponent from player's game data (from schedule, not props)
    setOpponentId(player.opponentId || null);
    setOpponentName(player.opponentName || null);

    const loadPlayerProps = async () => {
      setIsLoadingProps(true);
      try {
        const response = await fetchPlayerProps(playerId);
        setPlayerProps(response.props);
        // Don't override opponent from props - use schedule data instead
      } catch (err) {
        console.error('Failed to fetch player props:', err);
        setPlayerProps([]);
      } finally {
        setIsLoadingProps(false);
      }
    };

    loadPlayerProps();
  }, [player?.id, player?.opponentId, player?.opponentName]);

  // Fetch play type matchup when player and opponent are available
  useEffect(() => {
    if (!player || !opponentId) {
      setPlayTypeMatchups([]);
      return;
    }

    const playerId = parseInt(player.id, 10);
    if (isNaN(playerId)) {
      setPlayTypeMatchups([]);
      return;
    }

    const loadMatchups = async () => {
      setIsLoadingMatchups(true);
      try {
        const response = await fetchPlayTypeMatchup(playerId, opponentId);
        setPlayTypeMatchups(response.matchups);
      } catch (err) {
        console.error('Failed to fetch play type matchup:', err);
        setPlayTypeMatchups([]);
      } finally {
        setIsLoadingMatchups(false);
      }
    };

    loadMatchups();
  }, [player?.id, opponentId]);

  // Fetch game logs when player or gamesCount changes
  useEffect(() => {
    if (!player) {
      setGameLogs([]);
      return;
    }

    const loadGameLogs = async () => {
      setIsLoadingLogs(true);
      setLogsError(null);

      const playerId = parseInt(player.id, 10);
      if (isNaN(playerId)) {
        // Invalid player ID - skip fetching, show empty chart
        setGameLogs([]);
        setIsLoadingLogs(false);
        return;
      }

      try {
        const logs = await fetchPlayerGameLogs(playerId, gamesCount);
        setGameLogs(logs);
      } catch (err) {
        console.error('Failed to fetch game logs:', err);
        setLogsError(err instanceof Error ? err.message : 'Failed to load game data');
        setGameLogs([]);
      } finally {
        setIsLoadingLogs(false);
      }
    };

    loadGameLogs();
  }, [player?.id, gamesCount]);

  // Transform game logs to chart data based on selected stat
  const chartData: ChartDataPoint[] = useMemo(() => {
    if (gameLogs.length === 0) return [];
    return transformGameLogsToChartData(gameLogs, activeStat);
  }, [gameLogs, activeStat]);

  // Handle line changes from the chart
  const handleLineChange = useCallback((value: number, hitRateInfo: HitRateInfo) => {
    setCurrentLineValue(value);
    setCurrentHitRate(hitRateInfo);
  }, []);

  // Calculate season average based on selected stat category
  const seasonAvg = useMemo(() => {
    if (!playerStats) return null;
    const field = STAT_TO_API_FIELD[activeStat];
    const value = playerStats[field];
    // Return rounded to 1 decimal place
    return typeof value === 'number' ? Math.round(value * 10) / 10 : null;
  }, [playerStats, activeStat]);

  // Get the current prop line based on selected stat category
  const currentProp = useMemo(() => {
    const propStatName = STAT_CATEGORY_TO_PROP[activeStat];
    if (!propStatName) return null;
    return playerProps.find(p => p.statName === propStatName) || null;
  }, [playerProps, activeStat]);

  // Graph average will be same as season avg for now
  // Future: calculate from game logs based on selected window (Last 10, 15, 20, etc.)
  const graphAvg = seasonAvg;

  // Use dynamic values if available, otherwise fall back to static stats
  const displayLineValue = currentLineValue ?? stats?.line ?? 0;
  const displayHitRate = currentHitRate?.hitRate ?? stats?.hitRate ?? 0;
  const displayHitRateFraction = currentHitRate
    ? `${currentHitRate.hitCount}/${currentHitRate.totalGames}`
    : stats?.hitRateFraction ?? '0/0';

  // Track headshot image loading state
  const [imageError, setImageError] = useState(false);
  const headshotSrc = player ? `/assets/${player.id}.png` : '';

  // Reset image error state when player changes
  useEffect(() => {
    setImageError(false);
  }, [player?.id]);

  if (!player || !stats) {
    return (
      <main className="ml-[400px] pt-14 min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="text-6xl">🏀</div>
          <h2 className="text-xl font-semibold text-muted-foreground">Select a player</h2>
          <p className="text-sm text-muted-foreground max-w-[300px]">
            Choose a player from the sidebar to view their props and statistics
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="ml-[400px] pt-14 min-h-screen bg-background">
      <div className="p-6 space-y-6">
        {/* Stat Category Tabs */}
        <ScrollArea className="w-full">
          <div className="flex gap-1 pb-2">
            {STAT_CATEGORIES.map((stat) => (
              <button
                key={stat}
                onClick={() => setActiveStat(stat as StatCategory)}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-lg whitespace-nowrap transition-all duration-200',
                  activeStat === stat
                    ? 'bg-secondary text-foreground border-b-2 border-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
                )}
              >
                {stat}
              </button>
            ))}
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>

        {/* Player Header Section */}
        <div className="flex items-start justify-between gap-8 p-6 rounded-xl bg-card border border-border">
          {/* Left: Player Info */}
          <div className="flex items-start gap-4">
            {/* Avatar / Headshot with team color gradient outline */}
            <div className="relative">
              {(() => {
                const teamData = NBA_TEAMS[player.team as keyof typeof NBA_TEAMS];
                const primaryColor = teamData?.color || '#6366f1';
                const secondaryColor = teamData?.colorSecondary || '#8b5cf6';
                return (
                  <div
                    className="w-[88px] h-[88px] rounded-full p-1 flex items-center justify-center"
                    style={{
                      background: `linear-gradient(135deg, ${primaryColor}, ${secondaryColor})`,
                    }}
                  >
                    <div className="w-20 h-20 rounded-full bg-card flex items-center justify-center overflow-hidden">
                      {!imageError ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={headshotSrc}
                          alt={player.name}
                          width={80}
                          height={80}
                          className="object-cover w-full h-full"
                          onError={() => setImageError(true)}
                        />
                      ) : (
                        <span className="text-2xl font-bold text-foreground">
                          {player.name.split(' ').map(n => n[0]).join('')}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Name & Badges */}
            <div className="space-y-2">
              <div>
                <h2 className="text-xl font-semibold">{player.name}</h2>
                <p className="text-sm text-muted-foreground">{player.position}</p>
              </div>
              <div className="flex gap-2 flex-wrap">
                {player.badges?.map((badge) => (
                  <Badge
                    key={badge}
                    variant="secondary"
                    className="text-xs bg-muted/50 text-muted-foreground"
                  >
                    {badge}
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          {/* Center: Stats Grid */}
          <div className="flex gap-8">
            <div className="text-center">
              <div className="text-xs font-semibold text-muted-foreground tracking-wider uppercase mb-1">
                SZN AVG
              </div>
              <div className={cn(
                "text-3xl font-bold font-mono transition-colors duration-200",
                isLoadingStats ? "text-muted-foreground" : "text-foreground"
              )}>
                {isLoadingStats ? '—' : (seasonAvg ?? '—')}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs font-semibold text-muted-foreground tracking-wider uppercase mb-1">
                GRAPH AVG
              </div>
              <div className={cn(
                "text-3xl font-bold font-mono transition-colors duration-200",
                isLoadingStats ? "text-muted-foreground" : "text-foreground"
              )}>
                {isLoadingStats ? '—' : (graphAvg ?? '—')}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs font-semibold text-muted-foreground tracking-wider uppercase mb-1">
                HIT RATE
              </div>
              <div className={cn(
                "text-3xl font-bold font-mono transition-colors duration-200",
                displayHitRate < 50 ? "text-red-500" : "text-green-500"
              )}>
                {displayHitRate}%
                <span className="text-sm text-muted-foreground ml-1">
                  [{displayHitRateFraction}]
                </span>
              </div>
            </div>
          </div>

          {/* Right: Current Stat Prop Line */}
          <div className="flex items-center gap-3 p-4 rounded-xl bg-secondary/50 border border-border">
            {isLoadingProps ? (
              <div className="text-sm text-muted-foreground">Loading...</div>
            ) : currentProp ? (
              <>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Line</div>
                  <div className="text-xl font-bold font-mono">{currentProp.line}</div>
                </div>
                <div className="flex gap-2">
                  <button className="px-3 py-2 rounded-lg bg-green-500/20 text-green-500 font-semibold text-sm hover:bg-green-500/30 transition-colors">
                    O {formatOdds(currentProp.overOdds)}
                  </button>
                  <button className="px-3 py-2 rounded-lg bg-red-500/20 text-red-500 font-semibold text-sm hover:bg-red-500/30 transition-colors">
                    U {formatOdds(currentProp.underOdds)}
                  </button>
                </div>
              </>
            ) : (
              <div className="text-sm text-muted-foreground">No line available</div>
            )}
          </div>
        </div>

        {/* Filters Control Bar */}
        <div className="flex items-center gap-4 flex-wrap">
          {/* Season Selector */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-secondary/50">
            {seasons.map((season) => (
              <button
                key={season}
                onClick={() => setActiveSeason(season)}
                className={cn(
                  'px-3 py-1.5 text-sm font-medium rounded-md transition-all duration-200',
                  activeSeason === season
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {season}
              </button>
            ))}
          </div>

          {/* Games Slider */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary/50">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setGamesCount(Math.max(5, gamesCount - 5))}
            >
              <Minus className="h-3 w-3" />
            </Button>
            <div className="min-w-[60px] text-center">
              <span className="text-sm font-mono font-semibold">{gamesCount}</span>
              <span className="text-xs text-muted-foreground ml-1">games</span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setGamesCount(Math.min(82, gamesCount + 5))}
            >
              <Plus className="h-3 w-3" />
            </Button>
            <span className="text-xs text-muted-foreground">Max ({gamesCount})</span>
          </div>

          {/* Dropdowns */}
          <Button variant="outline" size="sm" className="h-8 text-xs">
            With/Out
          </Button>
          <Button variant="outline" size="sm" className="h-8 text-xs">
            Advanced Filters
          </Button>

          {/* Splits */}
          <div className="flex items-center gap-1">
            {splits.map((split) => (
              <Button
                key={split}
                variant="ghost"
                size="sm"
                className="h-8 text-xs text-muted-foreground hover:text-foreground"
              >
                {split}
              </Button>
            ))}
          </div>

          {/* Rankings Toggle */}
          <div className="ml-auto flex items-center gap-1 p-1 rounded-lg bg-secondary/50">
            <span className="text-xs text-muted-foreground px-2">Rankings</span>
            {(['All', 'L15'] as const).map((view) => (
              <button
                key={view}
                onClick={() => setRankingsView(view)}
                className={cn(
                  'px-3 py-1 text-xs font-medium rounded-md transition-all duration-200',
                  rankingsView === view
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {view}
              </button>
            ))}
          </div>
        </div>

        {/* Chart Section */}
        <div className="relative p-6 rounded-xl bg-card border border-border">
          {isLoadingLogs ? (
            <div className="w-full h-[450px] flex items-center justify-center">
              <div className="text-muted-foreground">Loading game data...</div>
            </div>
          ) : logsError ? (
            <div className="w-full h-[450px] flex items-center justify-center">
              <div className="text-destructive">{logsError}</div>
            </div>
          ) : (
            <StatsChart
              data={chartData}
              initialLineValue={currentProp?.line ?? seasonAvg ?? 20.5}
              onLineChange={handleLineChange}
            />
          )}

          {/* Legend */}
          <div className="flex items-center justify-end gap-6 mt-4 pt-4 border-t border-border">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-green-500" />
              <span className="text-xs text-muted-foreground">Over {displayLineValue}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-red-500" />
              <span className="text-xs text-muted-foreground">Under {displayLineValue}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded border-2 border-dashed border-muted-foreground" />
              <span className="text-xs text-muted-foreground">Upcoming</span>
            </div>
          </div>
        </div>

        {/* Play Type Analysis Card */}
        {opponentName && (
          <div className="p-6 rounded-xl bg-card border border-border">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Play Type Analysis</h3>
              <span className="text-sm text-muted-foreground">vs {opponentName}</span>
            </div>

            {isLoadingMatchups ? (
              <div className="text-sm text-muted-foreground text-center py-4">Loading matchups...</div>
            ) : playTypeMatchups.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-4">No play type data available</div>
            ) : (
              <div className="space-y-2">
                {/* Header */}
                <div className="grid grid-cols-4 gap-4 text-xs font-medium text-muted-foreground uppercase tracking-wider pb-2 border-b border-border">
                  <div>Play Type</div>
                  <div className="text-right">Player PPG</div>
                  <div className="text-right">Opp DEF Rank</div>
                  <div className="text-right">Opp PPP</div>
                </div>

                {/* Rows */}
                {playTypeMatchups.map((matchup) => (
                  <div key={matchup.playType} className="grid grid-cols-4 gap-4 py-2 text-sm border-b border-border/50 last:border-0">
                    <div className="font-medium">{matchup.playType}</div>
                    <div className="text-right font-mono">
                      {matchup.playerPpg.toFixed(1)}
                      <span className="text-muted-foreground ml-1">({matchup.pctOfTotal.toFixed(0)}%)</span>
                    </div>
                    <div className={cn(
                      "text-right font-mono font-semibold",
                      matchup.oppRank >= 21 ? "text-green-500" :
                      matchup.oppRank >= 11 ? "text-yellow-500" :
                      matchup.oppRank >= 6 ? "text-orange-500" :
                      "text-red-500"
                    )}>
                      #{matchup.oppRank}
                    </div>
                    <div className="text-right font-mono">{matchup.oppPpp.toFixed(3)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Shooting Zones Analysis Card */}
        {opponentName && opponentId && (
          <ShootingZonesCard
            playerId={parseInt(player.id)}
            opponentId={opponentId}
            opponentName={opponentName}
          />
        )}

        {/* Assist Zones Analysis Card */}
        {opponentName && opponentId && (
          <AssistZonesCard
            playerId={parseInt(player.id)}
            opponentId={opponentId}
            opponentName={opponentName}
          />
        )}
      </div>
    </main>
  );
}
