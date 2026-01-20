'use client';

import { useState, useMemo, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Search, Lock, ChevronDown, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { TeamLogo } from '@/components/ui/team-logo';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from '@/components/animate-ui/primitives/radix/collapsible';
import { Shine } from '@/components/animate-ui/primitives/effects/shine';
import {
  NBA_TEAMS,
  type Player,
  type GameMatchup,
} from '@/lib/data';
import { fetchUpcomingRosters, type ApiGameWithRosters, type ApiRosterPlayer } from '@/lib/api';

// Transform API roster player to frontend Player format
function transformRosterPlayer(
  player: ApiRosterPlayer,
  teamAbbr: string,
  opponentId?: number,
  opponentName?: string,
  opponentAbbr?: string
): Player {
  return {
    id: player.playerId.toString(),
    name: player.playerName,
    position: player.position || 'N/A',
    team: teamAbbr,
    isLocked: false,
    // No sportsbook data
    line: undefined,
    overOdds: undefined,
    underOdds: undefined,
    // Opponent info from game schedule
    opponentId,
    opponentName,
    opponentAbbr,
  };
}

// Transform API game to frontend GameMatchup format
function transformGame(game: ApiGameWithRosters): GameMatchup {
  const gameDate = new Date(game.gameDate + 'T00:00:00');
  return {
    id: game.gameId,
    homeTeam: game.homeTeam.abbreviation,
    awayTeam: game.awayTeam.abbreviation,
    time: game.gameStatus || game.gameTime,
    date: gameDate.toLocaleDateString('en-US', { month: 'short', day: '2-digit' }),
  };
}

interface PlayerRowProps {
  player: Player;
  isActive?: boolean;
  onClick?: () => void;
  compact?: boolean;
}

function PlayerRow({ player, isActive, onClick, compact }: PlayerRowProps) {
  const [imageError, setImageError] = useState(false);
  const headshotSrc = `/assets/${player.id}.png`;

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center justify-between rounded-lg cursor-pointer text-left',
        'transition-all duration-200 ease-out',
        'hover:scale-[1.01] active:scale-[0.99]',
        compact ? 'p-3' : 'p-4',
        isActive
          ? 'bg-primary/10 border border-primary/30 shadow-sm'
          : 'hover:bg-secondary/50'
      )}
    >
      <div className="flex items-center gap-3">
        {/* Avatar / Headshot */}
        <div className="relative">
          <div className={cn(
            "rounded-full bg-gradient-to-br from-muted to-muted/50 flex items-center justify-center overflow-hidden",
            "transition-transform duration-200",
            compact ? "w-10 h-10" : "w-12 h-12"
          )}>
            {!imageError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={headshotSrc}
                alt={player.name}
                width={compact ? 40 : 48}
                height={compact ? 40 : 48}
                className="object-cover w-full h-full"
                onError={() => setImageError(true)}
              />
            ) : (
              <span className={cn(
                "font-semibold text-muted-foreground",
                compact ? "text-sm" : "text-base"
              )}>
                {player.name.split(' ').map(n => n[0]).join('')}
              </span>
            )}
          </div>
        </div>

        {/* Name */}
        <div>
          <div className={cn("font-medium", compact ? "text-sm" : "text-base")}>{player.name}</div>
          <div className={cn("text-muted-foreground", compact ? "text-xs" : "text-sm")}>{player.position}</div>
        </div>
      </div>

      {/* Betting Line or Lock */}
      {player.isLocked ? (
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-muted/50 text-sm font-medium text-muted-foreground">
          <Lock className="w-3.5 h-3.5" />
          <span>UNLOCK</span>
        </div>
      ) : player.line ? (
        <div className="flex items-center bg-card rounded-md overflow-hidden text-xs font-mono">
          <div className="px-2 py-1.5 bg-secondary font-semibold">{player.line}</div>
          <div className="px-2 py-1.5 bg-green-500/20 text-green-500 font-semibold">
            O{player.overOdds}
          </div>
          <div className="px-2 py-1.5 bg-red-500/20 text-red-500 font-semibold">
            U{player.underOdds}
          </div>
        </div>
      ) : null}
    </button>
  );
}

interface MatchupCardProps {
  game: GameMatchup;
  homePlayers: Player[];
  awayPlayers: Player[];
  isExpanded: boolean;
  onToggle: () => void;
  selectedPlayerId: string | null;
  onPlayerSelect: (player: Player) => void;
}

function MatchupCard({ game, homePlayers, awayPlayers, isExpanded, onToggle, selectedPlayerId, onPlayerSelect }: MatchupCardProps) {
  const [activeTab, setActiveTab] = useState<'home' | 'away'>('home');
  const homeTeam = NBA_TEAMS[game.homeTeam];
  const awayTeam = NBA_TEAMS[game.awayTeam];

  const currentPlayers = activeTab === 'home' ? homePlayers : awayPlayers;

  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <Shine
        enableOnHover
        color="white"
        opacity={0.15}
        duration={800}
        className="rounded-lg"
      >
        <div className="rounded-lg bg-secondary/30 overflow-hidden transition-shadow duration-200 hover:shadow-md">
        {/* Matchup Header Button */}
        <CollapsibleTrigger asChild>
          <button
            className={cn(
              "w-full flex items-center justify-between p-4 transition-all duration-200",
              "hover:bg-secondary/50",
              "active:scale-[0.99]"
            )}
          >
            {/* Home Team */}
            <div className="flex items-center gap-3">
              <TeamLogo team={game.homeTeam} size={36} />
              <span className="text-base font-semibold">{homeTeam?.short || game.homeTeam}</span>
            </div>

            {/* Time */}
            <div className="text-center px-4">
              <div className="text-xs text-muted-foreground">{game.date}</div>
              <div className="text-sm font-semibold text-primary">{game.time}</div>
            </div>

            {/* Away Team */}
            <div className="flex items-center gap-3">
              <span className="text-base font-semibold">{awayTeam?.short || game.awayTeam}</span>
              <TeamLogo team={game.awayTeam} size={36} />
            </div>

            {/* Expand Icon */}
            <ChevronDown
              className={cn(
                "w-5 h-5 text-muted-foreground ml-3",
                "transition-transform duration-300 ease-out",
                isExpanded && "rotate-180"
              )}
            />
          </button>
        </CollapsibleTrigger>

        {/* Animated Expandable Content */}
        <CollapsibleContent
          transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        >
          <div className="border-t border-border/50">
            {/* Home/Away Tabs */}
            <div className="flex border-b border-border/50">
              <button
                onClick={() => setActiveTab('home')}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium",
                  "transition-all duration-200",
                  "hover:scale-[1.02] active:scale-[0.98]",
                  activeTab === 'home'
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/30"
                )}
              >
                <TeamLogo team={game.homeTeam} size={20} />
                {homeTeam?.name || game.homeTeam}
              </button>
              <button
                onClick={() => setActiveTab('away')}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium",
                  "transition-all duration-200",
                  "hover:scale-[1.02] active:scale-[0.98]",
                  activeTab === 'away'
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/30"
                )}
              >
                <TeamLogo team={game.awayTeam} size={20} />
                {awayTeam?.name || game.awayTeam}
              </button>
            </div>

            {/* Player List */}
            <div className="p-3 space-y-2">
              {currentPlayers.length > 0 ? (
                currentPlayers.map((player) => (
                  <PlayerRow
                    key={player.id}
                    player={player}
                    isActive={player.id === selectedPlayerId}
                    onClick={() => onPlayerSelect(player)}
                    compact
                  />
                ))
              ) : (
                <div className="text-center py-4 text-sm text-muted-foreground">
                  No players available
                </div>
              )}
            </div>
          </div>
        </CollapsibleContent>
        </div>
      </Shine>
    </Collapsible>
  );
}

interface SidebarProps {
  selectedPlayer: Player | null;
  onPlayerSelect: (player: Player) => void;
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ selectedPlayer, onPlayerSelect, isOpen = false, onClose }: SidebarProps) {
  const [expandedGames, setExpandedGames] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [games, setGames] = useState<GameMatchup[]>([]);
  const [playersByTeam, setPlayersByTeam] = useState<Record<string, Player[]>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch data on mount
  useEffect(() => {
    async function loadData() {
      try {
        setIsLoading(true);
        setError(null);

        // Fetch upcoming games (today + tomorrow, already filtered by backend)
        const response = await fetchUpcomingRosters();
        const games = response.games;

        // Transform games
        const transformedGames = games.map(transformGame);
        setGames(transformedGames);

        // Build players by team map (only players with underdog props)
        const playersMap: Record<string, Player[]> = {};
        for (const game of games) {
          // Home players - opponent is away team
          playersMap[game.homeTeam.abbreviation] = game.homePlayers
            .filter(p => p.hasProps)
            .map(p => transformRosterPlayer(
              p,
              game.homeTeam.abbreviation,
              game.awayTeam.id,
              game.awayTeam.name,
              game.awayTeam.abbreviation
            ));
          // Away players - opponent is home team
          playersMap[game.awayTeam.abbreviation] = game.awayPlayers
            .filter(p => p.hasProps)
            .map(p => transformRosterPlayer(
              p,
              game.awayTeam.abbreviation,
              game.homeTeam.id,
              game.homeTeam.name,
              game.homeTeam.abbreviation
            ));
        }
        setPlayersByTeam(playersMap);

        // Expand first game by default and auto-select first player with props
        if (transformedGames.length > 0 && games.length > 0) {
          setExpandedGames(new Set([transformedGames[0].id]));

          // Auto-select first player with props from first game's home team
          const firstGame = games[0];
          const firstHomePlayerWithProps = firstGame?.homePlayers.find(p => p.hasProps);
          if (firstHomePlayerWithProps) {
            const player = transformRosterPlayer(
              firstHomePlayerWithProps,
              firstGame.homeTeam.abbreviation,
              firstGame.awayTeam.id,
              firstGame.awayTeam.name,
              firstGame.awayTeam.abbreviation
            );
            onPlayerSelect(player);
          }
        }
      } catch (err) {
        console.error('Failed to load roster data:', err);
        setError('Failed to load games');
      } finally {
        setIsLoading(false);
      }
    }

    loadData();
  }, [onPlayerSelect]);

  // Get all players for search
  const allPlayers = useMemo(() => {
    return Object.values(playersByTeam).flat();
  }, [playersByTeam]);

  // Filter players based on search
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const query = searchQuery.toLowerCase();
    return allPlayers.filter(
      (player) =>
        player.name.toLowerCase().includes(query) ||
        player.team.toLowerCase().includes(query) ||
        NBA_TEAMS[player.team]?.name.toLowerCase().includes(query)
    );
  }, [searchQuery, allPlayers]);

  const toggleGame = (gameId: string) => {
    setExpandedGames((prev) => {
      const next = new Set(prev);
      if (next.has(gameId)) {
        next.delete(gameId);
      } else {
        next.add(gameId);
      }
      return next;
    });
  };

  const handlePlayerSelect = (player: Player) => {
    onPlayerSelect(player);
    setSearchQuery(''); // Clear search when player is selected
  };

  // Determine header text based on games
  const headerText = useMemo(() => {
    if (games.length === 0) return "Upcoming Games";
    // Check if we have games from multiple dates
    const dates = [...new Set(games.map(g => g.date))];
    if (dates.length === 1) {
      return `Games - ${dates[0]}`;
    }
    return "Upcoming Games";
  }, [games]);

  return (
    <aside className={cn(
      "fixed top-14 bottom-0 bg-sidebar border-r border-sidebar-border flex flex-col z-40",
      "w-[var(--sidebar-width)] left-0",
      "transition-transform duration-300 ease-in-out",
      // Desktop: always visible
      "lg:translate-x-0",
      // Mobile: slide in/out based on isOpen
      isOpen ? "translate-x-0" : "max-lg:-translate-x-full"
    )}>
      {/* Header Filters */}
      <div className="p-4 space-y-3 border-b border-sidebar-border">
        <div className="flex gap-2">
          <Select defaultValue="points">
            <SelectTrigger className="flex-1 h-9 bg-secondary/50 border-0">
              <SelectValue placeholder="Stat" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="points">Points</SelectItem>
              <SelectItem value="assists">Assists</SelectItem>
              <SelectItem value="rebounds">Rebounds</SelectItem>
              <SelectItem value="threes">Threes</SelectItem>
            </SelectContent>
          </Select>

          <Select defaultValue="all">
            <SelectTrigger className="flex-1 h-9 bg-secondary/50 border-0">
              <SelectValue placeholder="Games" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Games</SelectItem>
              <SelectItem value="today">Today</SelectItem>
              <SelectItem value="tomorrow">Tomorrow</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search players or teams..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9 bg-secondary/50 border-0 focus-visible:ring-1 focus-visible:ring-primary"
          />
        </div>

        {/* Search Results Dropdown */}
        {searchResults.length > 0 && (
          <div className="absolute left-4 right-4 top-[120px] z-50 bg-popover border border-border rounded-lg shadow-xl max-h-[300px] overflow-y-auto">
            <div className="p-2 space-y-1">
              {searchResults.map((player) => (
                <PlayerRow
                  key={player.id}
                  player={player}
                  isActive={player.id === selectedPlayer?.id}
                  onClick={() => handlePlayerSelect(player)}
                  compact
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Games List */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4 space-y-3">
          <h3 className="text-xs font-semibold text-muted-foreground tracking-wider uppercase">
            {headerText}
          </h3>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              {error}
            </div>
          ) : games.length === 0 ? (
            <div className="text-center py-8 px-4">
              <div className="text-sm text-muted-foreground">No game data available</div>
              <div className="text-xs text-muted-foreground/70 mt-1">
                Check back later for upcoming games
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {games.map((game) => (
                <MatchupCard
                  key={game.id}
                  game={game}
                  homePlayers={playersByTeam[game.homeTeam] || []}
                  awayPlayers={playersByTeam[game.awayTeam] || []}
                  isExpanded={expandedGames.has(game.id)}
                  onToggle={() => toggleGame(game.id)}
                  selectedPlayerId={selectedPlayer?.id || null}
                  onPlayerSelect={handlePlayerSelect}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
