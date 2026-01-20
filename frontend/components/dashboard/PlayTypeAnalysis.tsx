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
    <div className="p-6 rounded-xl bg-card border border-border">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Play Type Analysis</h3>
        <span className="text-sm text-muted-foreground">vs {opponentName}</span>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground text-center py-4">Loading matchups...</div>
      ) : error ? (
        <ErrorState message={error} onRetry={onRetry} className="py-4" />
      ) : matchups.length === 0 ? (
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
          {matchups.map((matchup) => (
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
  );
}
