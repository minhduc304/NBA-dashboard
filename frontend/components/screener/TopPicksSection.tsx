'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { ApiTopPick, ApiSharpBookLine } from '@/lib/api';
import { ChevronRight } from 'lucide-react';

const STAT_LABELS: Record<string, string> = {
  points: 'PTS',
  rebounds: 'REB',
  assists: 'AST',
  threes: '3PM',
  pts_rebs_asts: 'PRA',
  pts_asts: 'P+A',
  pts_rebs: 'P+R',
  rebs_asts: 'R+A',
  steals: 'STL',
  blocks: 'BLK',
  turnovers: 'TOV',
  blks_stls: 'B+S',
  free_throws_made: 'FTM',
  three_points_made: '3PM',
};

const BOOK_LABELS: Record<string, string> = {
  draftkings: 'DraftKings',
  fanduel: 'FanDuel',
  betmgm: 'BetMGM',
};

const BOOK_SHORT: Record<string, string> = {
  draftkings: 'DK',
  fanduel: 'FD',
  betmgm: 'MGM',
};

function formatOdds(odds: number | null): string {
  if (odds === null) return '-';
  return odds > 0 ? `+${odds}` : `${odds}`;
}

function formatMatchup(home: string, away: string): string {
  const short = (name: string) => {
    const abbrevs: Record<string, string> = {
      'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
      'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
      'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
      'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
      'Los Angeles Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
      'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
      'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
      'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
      'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
      'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS',
    };
    return abbrevs[name] || name.split(' ').pop() || name;
  };
  return `${short(away)} @ ${short(home)}`;
}

function titleCase(name: string): string {
  return name.replace(/\b\w/g, (c) => c.toUpperCase());
}

interface TopPicksSectionProps {
  picks: ApiTopPick[];
  loading: boolean;
}

/** Number of columns in the main table (for colspan on expanded row) */
const COL_COUNT = 11;

function ExpandedDetail({ books, direction }: { books: ApiSharpBookLine[]; direction: string }) {
  const isOver = direction === 'OVER';
  const sorted = [...books].sort((a, b) => a.line - b.line);

  return (
    <tr>
      <td colSpan={COL_COUNT} className="px-0 py-0">
        <div className="bg-muted/30 px-12 py-3 border-b border-border/30">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[0.6rem] uppercase tracking-wider text-muted-foreground">
                <th className="text-left pb-1.5 font-medium">Book</th>
                <th className="text-right pb-1.5 font-medium">Line</th>
                <th className="text-right pb-1.5 font-medium">{isOver ? 'Over' : 'Under'}</th>
                <th className="text-right pb-1.5 font-medium text-muted-foreground/50">{isOver ? 'Under' : 'Over'}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((book) => (
                <tr key={book.sportsbook} className="border-t border-border/20">
                  <td className="py-1.5 font-medium">{BOOK_LABELS[book.sportsbook] || book.sportsbook}</td>
                  <td className="py-1.5 text-right font-mono tabular-nums">{book.line}</td>
                  <td className="py-1.5 text-right font-mono tabular-nums">
                    {formatOdds(isOver ? book.overOdds : book.underOdds)}
                  </td>
                  <td className="py-1.5 text-right font-mono tabular-nums text-muted-foreground/40">
                    {formatOdds(isOver ? book.underOdds : book.overOdds)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </td>
    </tr>
  );
}

function PickRow({ pick, rank }: { pick: ApiTopPick; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const isOver = pick.direction === 'OVER';

  return (
    <>
      <tr
        className="h-11 border-b border-border/30 hover:bg-surface-hover duration-150 ease-out cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 font-mono text-xs text-muted-foreground/60">{rank}</td>
        <td className="px-3 font-medium whitespace-nowrap">
          <div className="flex items-center gap-1.5">
            <ChevronRight className={cn(
              'w-3.5 h-3.5 text-muted-foreground/50 transition-transform',
              expanded && 'rotate-90',
            )} />
            {titleCase(pick.playerName)}
          </div>
        </td>
        <td className="px-3 whitespace-nowrap">
          <span className="inline-block px-2 py-0.5 rounded-sm text-xs font-mono bg-secondary text-secondary-foreground">
            {STAT_LABELS[pick.statType] || pick.statType}
          </span>
        </td>
        <td className="px-3 text-center">
          <span className={cn(
            'text-xs font-semibold px-1.5 py-0.5 rounded-sm',
            isOver ? 'bg-success/15 text-success' : 'bg-destructive/15 text-destructive',
          )}>
            {pick.direction}
          </span>
        </td>
        <td className="px-3 text-right font-mono tabular-nums">{pick.udLine}</td>
        <td className="px-3 text-right font-mono tabular-nums text-muted-foreground">
          {pick.udOdds !== null ? formatOdds(pick.udOdds) : '-110'}
        </td>
        <td className={cn(
          'px-3 text-right font-mono tabular-nums font-bold',
          isOver ? 'text-success' : 'text-destructive',
        )}>
          {pick.edgePct.toFixed(1)}%
        </td>
        <td className="px-3 text-right font-mono tabular-nums text-muted-foreground">
          {pick.bestBookDeviggedProb}%
        </td>
        <td className="px-3 text-right font-mono tabular-nums text-muted-foreground">
          {pick.udImpliedProb}%
        </td>
        <td className="px-3 text-center text-xs text-muted-foreground">
          {BOOK_SHORT[pick.bestBook] || pick.bestBook}
        </td>
        <td className="px-3 text-xs font-mono text-muted-foreground whitespace-nowrap">
          {formatMatchup(pick.homeTeam, pick.awayTeam)}
        </td>
      </tr>
      {expanded && <ExpandedDetail books={pick.books} direction={pick.direction} />}
    </>
  );
}

function LoadingSkeleton() {
  return (
    <div className="card-surface rounded-lg overflow-hidden">
      <div className="p-4 space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-4 animate-pulse">
            <div className="h-4 bg-muted rounded w-8" />
            <div className="h-4 bg-muted rounded w-32" />
            <div className="h-4 bg-muted rounded w-12" />
            <div className="h-4 bg-muted rounded w-16" />
            <div className="h-4 bg-muted rounded w-20 ml-auto" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function TopPicksSection({ picks, loading }: TopPicksSectionProps) {
  if (loading) return <LoadingSkeleton />;

  if (picks.length === 0) {
    return (
      <div className="card-surface rounded-lg flex items-center justify-center h-48 text-muted-foreground text-sm">
        No Underdog picks with sharp book matches found for today.
      </div>
    );
  }

  return (
    <div className="card-surface rounded-lg overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left px-4 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground w-8">#</th>
            <th className="text-left px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">Player</th>
            <th className="text-left px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">Stat</th>
            <th className="text-center px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">Dir</th>
            <th className="text-right px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">UD Line</th>
            <th className="text-right px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">UD Odds</th>
            <th className="text-right px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">Edge</th>
            <th className="text-right px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">Fair %</th>
            <th className="text-right px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">Implied %</th>
            <th className="text-center px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">Best Book</th>
            <th className="text-left px-3 py-3 text-[0.65rem] uppercase tracking-[0.08em] text-muted-foreground">Game</th>
          </tr>
        </thead>
        <tbody>
          {picks.map((pick, i) => (
            <PickRow key={`${pick.playerName}-${pick.statType}`} pick={pick} rank={i + 1} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
