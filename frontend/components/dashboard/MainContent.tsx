'use client';

import { useMemo, useState, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Minus, Plus, SlidersHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { STAT_CATEGORIES, STAT_TO_API_FIELD, getPlayerStats, transformGameLogsToChartData, type Player, type StatCategory, type ChartDataPoint } from '@/lib/data';
import { fetchPlayerGameLogs, fetchPlayerById, fetchPlayerProps, fetchPlayTypeMatchup, fetchUpcomingMatchupContext, type ApiGameLog, type ApiPlayer, type ApiPropLine, type ApiPlayTypeMatchup, type ApiUpcomingMatchupContext } from '@/lib/api';
import { STAT_CATEGORY_TO_PROP } from '@/lib/constants';
import { StatsChart, type HitRateInfo } from './StatsChart';
import { ShootingZonesCard } from './ShootingZonesCard';
import { AssistZonesCard } from './AssistZonesCard';
import { PlayerHeader } from './PlayerHeader';
import { PlayTypeAnalysis } from './PlayTypeAnalysis';
import { FilterPanel, DEFAULT_FILTERS, type GameLogFilters } from './FilterPanel';
import { ErrorState } from '@/components/ui/error-state';

interface MainContentProps {
  player: Player | null;
}

export function MainContent({ player }: MainContentProps) {
  const [activeStat, setActiveStat] = useState<StatCategory>('Points');
  const [gamesCount, setGamesCount] = useState(20);

  // Filter panel state
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false);
  const [filters, setFilters] = useState<GameLogFilters>(DEFAULT_FILTERS);

  // Dynamic line value and hit rate from chart interaction
  const [currentLineValue, setCurrentLineValue] = useState<number | null>(null);
  const [currentHitRate, setCurrentHitRate] = useState<HitRateInfo | null>(null);

  // Game logs state
  const [gameLogs, setGameLogs] = useState<ApiGameLog[]>([]);
  const [isLoadingLogs, setIsLoadingLogs] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [logsRetryCount, setLogsRetryCount] = useState(0);

  // Retry handler for game logs
  const handleRetryLogs = useCallback(() => {
    setLogsRetryCount(prev => prev + 1);
  }, []);

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
  const [matchupsError, setMatchupsError] = useState<string | null>(null);
  const [matchupsRetryCount, setMatchupsRetryCount] = useState(0);

  // Upcoming game defensive context state
  const [upcomingContext, setUpcomingContext] = useState<ApiUpcomingMatchupContext | null>(null);

  // Retry handler for play type matchups
  const handleRetryMatchups = useCallback(() => {
    setMatchupsRetryCount(prev => prev + 1);
  }, []);

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
      setMatchupsError(null);
      return;
    }

    const playerId = parseInt(player.id, 10);
    if (isNaN(playerId)) {
      setPlayTypeMatchups([]);
      setMatchupsError(null);
      return;
    }

    const loadMatchups = async () => {
      setIsLoadingMatchups(true);
      setMatchupsError(null);
      try {
        const response = await fetchPlayTypeMatchup(playerId, opponentId);
        setPlayTypeMatchups(response.matchups);
      } catch (err) {
        console.error('Failed to fetch play type matchup:', err);
        setMatchupsError('Unable to load play type data');
        setPlayTypeMatchups([]);
      } finally {
        setIsLoadingMatchups(false);
      }
    };

    loadMatchups();
  }, [player?.id, opponentId, matchupsRetryCount]);

  // Fetch upcoming matchup defensive context when player, opponent, and stat category are available
  useEffect(() => {
    if (!player || !opponentId) {
      setUpcomingContext(null);
      return;
    }

    const playerId = parseInt(player.id, 10);
    if (isNaN(playerId)) {
      setUpcomingContext(null);
      return;
    }

    // Map stat category to backend stat_type
    let statType = 'points';
    if (activeStat === 'Assists' || activeStat === 'Ast+Reb') {
      statType = 'assists';
    } else if (activeStat === 'Rebounds') {
      statType = 'rebounds';
    }

    const loadUpcomingContext = async () => {
      try {
        const context = await fetchUpcomingMatchupContext(playerId, opponentId, statType);
        setUpcomingContext(context);
      } catch (err) {
        console.error('Failed to fetch upcoming matchup context:', err);
        setUpcomingContext(null);
      }
    };

    loadUpcomingContext();
  }, [player?.id, opponentId, activeStat]);

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
        // Map stat category to backend column name
        const statColumn = STAT_TO_API_FIELD[activeStat];
        const statCategoryParam = typeof statColumn === 'string' ? statColumn : statColumn[0];

        const logs = await fetchPlayerGameLogs(playerId, gamesCount, statCategoryParam);
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
  }, [player?.id, gamesCount, activeStat, logsRetryCount]);

  // Get the current prop line based on selected stat category
  // (moved here so chartData can use it)
  const currentProp = useMemo(() => {
    const propStatName = STAT_CATEGORY_TO_PROP[activeStat];
    if (!propStatName) return null;
    return playerProps.find(p => p.statName === propStatName) || null;
  }, [playerProps, activeStat]);

  // Transform game logs to chart data based on selected stat
  // Also add upcoming game as a future data point if opponent is available
  const chartData: ChartDataPoint[] = useMemo(() => {
    if (gameLogs.length === 0) return [];

    const transformed = transformGameLogsToChartData(gameLogs, activeStat);

    // Add upcoming game as a future data point if we have opponent info
    if (opponentId && player?.opponentAbbr) {
      // Calculate the bar height: use prop line if available, otherwise L10 average
      let futureValue: number | null = null;

      if (currentProp?.line) {
        futureValue = currentProp.line;
      } else if (transformed.length > 0) {
        // Calculate L10 average from the most recent games
        const recentGames = transformed.slice(-10).filter(d => d.value !== null);
        if (recentGames.length > 0) {
          futureValue = recentGames.reduce((sum, d) => sum + (d.value || 0), 0) / recentGames.length;
        }
      }

      // Get today's date for display
      const today = new Date();
      const futureDate = today.toLocaleDateString('en-US', { month: 'short', day: '2-digit' });

      const futureGame: ChartDataPoint = {
        date: futureDate,
        opponent: player.opponentAbbr,
        opponentId: opponentId,
        value: futureValue,
        isOver: false,
        isFuture: true,
        wl: null,
        gameMargin: null,
        min: null,
        fgm: null,
        fga: null,
        fg3m: null,
        fg3a: null,
        ftm: null,
        fta: null,
        oreb: null,
        dreb: null,
        dnpPlayers: [],
        upcomingContext: upcomingContext || undefined,
      };

      transformed.push(futureGame);
    }

    return transformed;
  }, [gameLogs, activeStat, opponentId, player?.opponentAbbr, currentProp?.line, upcomingContext]);

  // Extract available seasons from game logs
  const availableSeasons = useMemo(() => {
    const seasons = new Set<string>();
    gameLogs.forEach((log) => {
      if (log.season) seasons.add(log.season);
    });
    return Array.from(seasons).sort();
  }, [gameLogs]);

  // Extract available opponents from game logs
  const availableOpponents = useMemo(() => {
    const opponents = new Set<string>();
    gameLogs.forEach((log) => {
      if (log.matchup) {
        // Matchup format: "LAL vs. GSW" or "LAL @ GSW"
        const parts = log.matchup.split(/\s+(?:vs\.|@)\s+/);
        if (parts.length === 2) {
          opponents.add(parts[1]);
        }
      }
    });
    return Array.from(opponents).sort();
  }, [gameLogs]);

  // Filter game logs based on active filters
  const filteredGameLogs = useMemo(() => {
    return gameLogs.filter((log) => {
      // Season filter
      if (filters.season !== 'all' && log.season !== filters.season) {
        return false;
      }

      // Location filter (home vs away)
      if (filters.location === 'home' && !log.matchup?.includes('vs.')) {
        return false;
      }
      if (filters.location === 'away' && !log.matchup?.includes('@')) {
        return false;
      }

      // Result filter (win vs loss)
      if (filters.result === 'win' && log.wl !== 'W') {
        return false;
      }
      if (filters.result === 'loss' && log.wl !== 'L') {
        return false;
      }

      // Opponent filter
      if (filters.opponentAbbr) {
        const parts = log.matchup?.split(/\s+(?:vs\.|@)\s+/) || [];
        const opponent = parts[1];
        if (opponent !== filters.opponentAbbr) {
          return false;
        }
      }

      return true;
    });
  }, [gameLogs, filters]);

  // Transform filtered game logs to chart data (includes future game from chartData)
  const filteredChartData: ChartDataPoint[] = useMemo(() => {
    if (filteredGameLogs.length === 0 && !chartData.some(d => d.isFuture)) return [];

    const transformed = transformGameLogsToChartData(filteredGameLogs, activeStat);

    // Add the future game from chartData if it exists
    const futureGame = chartData.find(d => d.isFuture);
    if (futureGame) {
      transformed.push(futureGame);
    }

    return transformed;
  }, [filteredGameLogs, activeStat, chartData]);

  // Reset filters when player changes
  useEffect(() => {
    setFilters(DEFAULT_FILTERS);
    setIsFilterPanelOpen(false);
  }, [player?.id]);

  // Count active filters for badge
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.season !== 'all') count++;
    if (filters.location !== 'all') count++;
    if (filters.result !== 'all') count++;
    if (filters.opponentAbbr) count++;
    return count;
  }, [filters]);

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

  // Filter stat categories to only show those with available props
  const availableStatCategories = useMemo(() => {
    if (playerProps.length === 0) return STAT_CATEGORIES; // Show all while loading

    return STAT_CATEGORIES.filter(stat => {
      const propStatName = STAT_CATEGORY_TO_PROP[stat];
      if (!propStatName) return false;
      return playerProps.some(p => p.statName === propStatName);
    });
  }, [playerProps]);

  // Auto-select first available stat when props load or player changes
  useEffect(() => {
    if (availableStatCategories.length > 0 && !availableStatCategories.includes(activeStat)) {
      setActiveStat(availableStatCategories[0] as StatCategory);
    }
  }, [availableStatCategories, activeStat]);

  // Graph average will be same as season avg for now
  const graphAvg = seasonAvg;

  // Use dynamic values if available, otherwise fall back to static stats
  const displayLineValue = currentLineValue ?? stats?.line ?? 0;
  const displayHitRate = currentHitRate?.hitRate ?? stats?.hitRate ?? 0;
  const displayHitRateFraction = currentHitRate
    ? `${currentHitRate.hitCount}/${currentHitRate.totalGames}`
    : stats?.hitRateFraction ?? '0/0';

  if (!player || !stats) {
    return (
      <main className="lg:ml-[var(--sidebar-width)] pt-14 min-h-screen bg-background flex items-center justify-center">
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
    <main className="lg:ml-[var(--sidebar-width)] pt-14 min-h-screen bg-background">
      <div className="p-4 lg:p-6 space-y-4 lg:space-y-6">
        {/* Stat Category Tabs - Only show categories with available props */}
        <div className="relative">
          <ScrollArea className="w-full">
            <div className="flex gap-1 pb-2">
              {isLoadingProps ? (
                <div className="px-4 py-2 text-sm text-muted-foreground">Loading props...</div>
              ) : availableStatCategories.length === 0 ? (
                <div className="px-4 py-2 text-sm text-muted-foreground">No props available for this player</div>
              ) : (
                availableStatCategories.map((stat) => (
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
                ))
              )}
            </div>
            <ScrollBar orientation="horizontal" />
          </ScrollArea>
          {/* Right fade gradient when scrollable */}
          <div className="absolute right-0 top-0 bottom-2 w-8 bg-gradient-to-l from-background to-transparent pointer-events-none" />
        </div>

        {/* Player Header Section */}
        <PlayerHeader
          player={player}
          seasonAvg={seasonAvg}
          graphAvg={graphAvg}
          hitRate={displayHitRate}
          hitRateFraction={displayHitRateFraction}
          currentProp={currentProp}
          isLoadingStats={isLoadingStats}
          isLoadingProps={isLoadingProps}
        />

        {/* Simplified Filters Control Bar */}
        <div className="flex items-center gap-4">
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
          </div>

          {/* Active filter summary */}
          {activeFilterCount > 0 && (
            <div className="text-xs text-muted-foreground">
              {filteredGameLogs.length} of {gameLogs.length} games
            </div>
          )}

          {/* Filter Panel Toggle Button */}
          <Button
            variant={isFilterPanelOpen ? 'secondary' : 'outline'}
            size="sm"
            className="ml-auto h-8 gap-2"
            onClick={() => setIsFilterPanelOpen(!isFilterPanelOpen)}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            <span>Filters</span>
            {activeFilterCount > 0 && (
              <Badge variant="secondary" className="h-5 w-5 p-0 flex items-center justify-center text-xs">
                {activeFilterCount}
              </Badge>
            )}
          </Button>
        </div>

        {/* Chart Section with Filter Panel */}
        <div className="flex gap-4">
          {/* Chart Card - uses explicit width transition */}
          <div
            className="relative p-6 rounded-xl bg-card border border-border transition-[width] duration-300 ease-out overflow-hidden"
            style={{ width: isFilterPanelOpen ? 'calc(100% - 296px)' : '100%' }}
          >
            {isLoadingLogs ? (
              <div className="w-full h-[450px] flex items-center justify-center">
                <div className="text-muted-foreground">Loading game data...</div>
              </div>
            ) : logsError ? (
              <div className="w-full h-[450px] flex items-center justify-center">
                <ErrorState message={logsError} onRetry={handleRetryLogs} />
              </div>
            ) : filteredChartData.length === 0 ? (
              <div className="w-full h-[450px] flex items-center justify-center">
                <div className="text-center space-y-2">
                  <div className="text-muted-foreground">No games match the selected filters</div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setFilters(DEFAULT_FILTERS)}
                  >
                    Clear filters
                  </Button>
                </div>
              </div>
            ) : (
              <StatsChart
                data={filteredChartData}
                initialLineValue={currentProp?.line ?? seasonAvg ?? 20.5}
                onLineChange={handleLineChange}
                statCategory={activeStat}
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

          {/* Filter Panel - Slides in from right */}
          <div
            className={cn(
              "rounded-xl bg-card border border-border overflow-hidden transition-all duration-300 ease-out flex-shrink-0",
              isFilterPanelOpen
                ? "w-[280px] opacity-100"
                : "w-0 opacity-0 pointer-events-none"
            )}
          >
            <FilterPanel
              isOpen={isFilterPanelOpen}
              filters={filters}
              onFiltersChange={setFilters}
              onClose={() => setIsFilterPanelOpen(false)}
              availableOpponents={availableOpponents}
              availableSeasons={availableSeasons}
            />
          </div>
        </div>

        {/* Play Type Analysis Card */}
        {opponentName && (
          <PlayTypeAnalysis
            matchups={playTypeMatchups}
            opponentName={opponentName}
            isLoading={isLoadingMatchups}
            error={matchupsError}
            onRetry={handleRetryMatchups}
          />
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
