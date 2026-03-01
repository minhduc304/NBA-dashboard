'use client';

import { cn } from '@/lib/utils';
import { type ApiPlayTypeMatchup } from '@/lib/api';
import { ErrorState } from '@/components/ui/error-state';

interface PlayTypeAnalysisProps {
  matchups: ApiPlayTypeMatchup[];
  opponentName: string;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function PlayTypeAnalysis({
  matchups,
  opponentName,
  isLoading,
  error,
  onRetry,
}: PlayTypeAnalysisProps) {
  return (
    <div className="card-surface rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-sm font-semibold text-foreground">Play Type Analysis</h3>
        <span className="label-meta">vs {opponentName}</span>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground text-center py-4">Loading matchups...</div>
      ) : error ? (
        <ErrorState message={error} onRetry={onRetry} className="py-4" />
      ) : matchups.length === 0 ? (
        <div className="text-sm text-muted-foreground text-center py-4">No play type data available</div>
      ) : (
        <div>
          {/* Header */}
          <div className="grid grid-cols-4 gap-4 pb-2 border-b border-border/40">
            <div className="label-meta">Play Type</div>
            <div className="label-meta text-right">Player PPG</div>
            <div className="label-meta text-right">Opp DEF Rank</div>
            <div className="label-meta text-right">Opp PPP</div>
          </div>

          {/* Rows */}
          {matchups.map((matchup) => (
            <div
              key={matchup.playType}
              className="grid grid-cols-4 gap-4 py-2.5 border-b border-border/40 last:border-0 duration-150 ease-out hover:bg-surface-hover"
            >
              <div className="font-sans text-sm font-medium text-foreground">{matchup.playType}</div>
              <div className="text-right font-mono text-sm text-foreground">
                {matchup.playerPpg.toFixed(1)}
                <span className="font-mono text-xs text-muted-foreground ml-1">({matchup.pctOfTotal.toFixed(0)}%)</span>
              </div>
              <div className="text-right">
                <span className="text-muted-foreground font-mono text-sm">#</span>
                <span className={cn(
                  "font-mono text-sm",
                  matchup.oppRank >= 26 ? "text-success font-bold" :
                  matchup.oppRank <= 5 ? "text-destructive font-bold" :
                  "text-muted-foreground"
                )}>
                  {matchup.oppRank}
                </span>
              </div>
              <div className="text-right font-mono text-sm text-muted-foreground">{matchup.oppPpp.toFixed(3)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
