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
    line: undefined,
    overOdds: undefined,
    underOdds: undefined,
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
}

function PlayerRow({ player, isActive, onClick }: PlayerRowProps) {
  const [imageError, setImageError] = useState(false);
  const headshotSrc = `/assets/${player.id}.png`;

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center justify-between text-left h-11 px-3 border-l-2 duration-150 ease-out',
        isActive
          ? 'bg-surface-active border-l-accent'
          : 'border-l-transparent hover:bg-surface-hover hover:border-l-accent'
      )}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        {/* Avatar */}
        <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center overflow-hidden shrink-0">
          {!imageError ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={headshotSrc}
              alt={player.name}
              width={28}
              height={28}
              className="object-cover w-full h-full"
              onError={() => setImageError(true)}
            />
          ) : (
            <span className="font-mono text-[10px] text-muted-foreground">
              {player.name.split(' ').map(n => n[0]).join('')}
            </span>
          )}
        </div>

        {/* Name + Position */}
        <div className="min-w-0">
          <div className={cn(
            'font-sans text-sm truncate',
            isActive ? 'font-semibold text-foreground' : 'font-medium text-foreground'
          )}>
            {player.name}
          </div>
          <div className="font-sans text-xs text-muted-foreground">{player.position}</div>
        </div>
      </div>

      {/* Betting Line or Lock */}
      {player.isLocked ? (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-sm bg-muted text-xs font-mono text-muted-foreground shrink-0">
          <Lock className="w-3 h-3" />
          <span>UNLOCK</span>
        </div>
      ) : player.line ? (
        <div className="flex items-center rounded-sm overflow-hidden text-xs font-mono shrink-0">
          <div className="px-2 py-1 bg-secondary font-semibold">{player.line}</div>
          <div className="px-2 py-1 bg-success/15 text-success font-semibold">
            O{player.overOdds}
          </div>
          <div className="px-2 py-1 bg-destructive/15 text-destructive font-semibold">
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
      <div className="border-b border-sidebar-border">
        {/* Matchup Header */}
        <CollapsibleTrigger asChild>
          <button
            className={cn(
              'w-full flex items-center justify-between px-3 py-2',
              'bg-popover duration-150 ease-out hover:bg-card'
            )}
          >
            <div className="flex items-center gap-2">
              <TeamLogo team={game.homeTeam} size={20} />
              <span className="font-mono text-xs text-foreground">{game.homeTeam}</span>
              <span className="font-sans text-xs text-muted-foreground">vs</span>
              <span className="font-mono text-xs text-foreground">{game.awayTeam}</span>
              <TeamLogo team={game.awayTeam} size={20} />
            </div>

            <div className="flex items-center gap-3">
              <span className="font-sans text-xs text-muted-foreground">
                {game.date} · {game.time}
              </span>
              <ChevronDown
                className={cn(
                  'w-4 h-4 text-muted-foreground duration-150 ease-out',
                  isExpanded && 'rotate-180'
                )}
              />
            </div>
          </button>
        </CollapsibleTrigger>

        {/* Expandable Content */}
        <CollapsibleContent
          transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        >
          {/* Home/Away Tabs */}
          <div className="flex border-b border-sidebar-border">
            <button
              onClick={() => setActiveTab('home')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 py-2 text-sm font-sans border-b-2 duration-150 ease-out',
                activeTab === 'home'
                  ? 'text-foreground border-accent'
                  : 'text-muted-foreground border-transparent hover:text-foreground'
              )}
            >
              <TeamLogo team={game.homeTeam} size={16} />
              {homeTeam?.name || game.homeTeam}
            </button>
            <button
              onClick={() => setActiveTab('away')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 py-2 text-sm font-sans border-b-2 duration-150 ease-out',
                activeTab === 'away'
                  ? 'text-foreground border-accent'
                  : 'text-muted-foreground border-transparent hover:text-foreground'
              )}
            >
              <TeamLogo team={game.awayTeam} size={16} />
              {awayTeam?.name || game.awayTeam}
            </button>
          </div>

          {/* Player List */}
          <div className="py-1">
            {currentPlayers.length > 0 ? (
              currentPlayers.map((player) => (
                <PlayerRow
                  key={player.id}
                  player={player}
                  isActive={player.id === selectedPlayerId}
                  onClick={() => onPlayerSelect(player)}
                />
              ))
            ) : (
              <div className="text-center py-4 text-xs text-muted-foreground">
                No players available
              </div>
            )}
          </div>
        </CollapsibleContent>
      </div>
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

        const response = await fetchUpcomingRosters();
        const games = response.games;

        const transformedGames = games.map(transformGame);
        setGames(transformedGames);

        const playersMap: Record<string, Player[]> = {};
        for (const game of games) {
          playersMap[game.homeTeam.abbreviation] = game.homePlayers
            .filter(p => p.hasProps)
            .map(p => transformRosterPlayer(
              p,
              game.homeTeam.abbreviation,
              game.awayTeam.id,
              game.awayTeam.name,
              game.awayTeam.abbreviation
            ));
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

        if (transformedGames.length > 0 && games.length > 0) {
          setExpandedGames(new Set([transformedGames[0].id]));

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

  const allPlayers = useMemo(() => {
    return Object.values(playersByTeam).flat();
  }, [playersByTeam]);

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
    setSearchQuery('');
  };

  const headerText = useMemo(() => {
    if (games.length === 0) return "Upcoming Games";
    const dates = [...new Set(games.map(g => g.date))];
    if (dates.length === 1) {
      return `Games — ${dates[0]}`;
    }
    return "Upcoming Games";
  }, [games]);

  return (
    <aside className={cn(
      "fixed top-12 bottom-0 bg-sidebar border-r border-sidebar-border flex flex-col z-40",
      "w-[var(--sidebar-width)] left-0",
      "transition-transform duration-300 ease-in-out",
      "lg:translate-x-0",
      isOpen ? "translate-x-0" : "max-lg:-translate-x-full"
    )}>
      {/* Filters */}
      <div className="p-3 space-y-2.5 border-b border-sidebar-border">
        <div className="flex gap-2">
          <Select defaultValue="points">
            <SelectTrigger className="flex-1 h-8 bg-secondary border-border text-sm">
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
            <SelectTrigger className="flex-1 h-8 bg-secondary border-border text-sm">
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
            placeholder="Search players..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-8 border-transparent focus-visible:border-ring"
          />
        </div>

        {/* Search Results Dropdown */}
        {searchResults.length > 0 && (
          <div className="absolute left-3 right-3 top-24 z-50 bg-popover border border-border rounded-md shadow-lg max-h-[300px] overflow-y-auto">
            <div className="py-1">
              {searchResults.map((player) => (
                <PlayerRow
                  key={player.id}
                  player={player}
                  isActive={player.id === selectedPlayer?.id}
                  onClick={() => handlePlayerSelect(player)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Games List */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-3 pt-3 pb-1">
          <h3 className="label-meta mb-2">
            {headerText}
          </h3>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
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
          <div>
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
    </aside>
  );
}
