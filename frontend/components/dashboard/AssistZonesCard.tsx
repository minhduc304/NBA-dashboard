'use client';

import { useEffect, useState, useCallback } from 'react';
import { Loader2 } from 'lucide-react';
import { AssistZonesCourt } from './AssistZonesCourt';
import { ErrorState } from '@/components/ui/error-state';
import {
  fetchAssistZoneMatchup,
  ApiAssistZoneMatchupResponse,
} from '@/lib/api';
import { sortZonesByAssists, formatAssistPct } from '@/lib/assist-zones';

interface AssistZonesCardProps {
  playerId: number;
  opponentId: number;
  opponentName: string;
}

export function AssistZonesCard({
  playerId,
  opponentId,
  opponentName,
}: AssistZonesCardProps) {
  const [data, setData] = useState<ApiAssistZoneMatchupResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const handleRetry = useCallback(() => {
    setRetryCount(prev => prev + 1);
  }, []);

  useEffect(() => {
    async function fetchData() {
      if (!playerId || !opponentId) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const matchupData = await fetchAssistZoneMatchup(playerId, opponentId);
        setData(matchupData);
      } catch (err) {
        console.error('Error fetching assist zone data:', err);
        setError('Unable to load assist zone data');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [playerId, opponentId, retryCount]);

  // Check if we have any data
  const hasData = data && data.zones.length > 0 && data.zones.some((z) => z.hasData);

  return (
    <div className="card-surface rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-sm font-semibold text-foreground">Assist Zones</h3>
        <span className="label-meta">vs {opponentName}</span>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading zones...</span>
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={handleRetry} />
      ) : !hasData ? (
        <div className="text-center py-8 text-sm text-muted-foreground">
          No assist zone data available
        </div>
      ) : (
        <div className="space-y-4">
          {/* Basketball Court Visualization */}
          <AssistZonesCourt
            zoneData={data!.zones}
            totalAssists={data!.totalAssists}
          />

          {/* Dual Legend */}
          <div className="space-y-2 pt-2">
            {/* Fill Color Legend */}
            <div className="flex items-center justify-center gap-3">
              <span className="text-xs text-muted-foreground">Fill:</span>
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-sm"
                    style={{ backgroundColor: 'var(--muted)' }}
                  />
                  <span className="text-muted-foreground">Low %</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-sm"
                    style={{ backgroundColor: 'var(--primary)' }}
                  />
                  <span className="text-muted-foreground">High %</span>
                </div>
              </div>
            </div>

            {/* Border Color Legend */}
            <div className="flex items-center justify-center gap-3">
              <span className="text-xs text-muted-foreground">Border:</span>
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-sm border-2"
                    style={{ borderColor: 'var(--success)' }}
                  />
                  <span className="text-muted-foreground">Weak DEF</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-sm border-2"
                    style={{ borderColor: 'var(--accent)' }}
                  />
                  <span className="text-muted-foreground">Avg DEF</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-sm border-2"
                    style={{ borderColor: 'var(--destructive)' }}
                  />
                  <span className="text-muted-foreground">Strong DEF</span>
                </div>
              </div>
            </div>
          </div>

          {/* Top Zones Summary */}
          {data && (
            <div className="pt-4 border-t border-border">
              <h4 className="label-meta mb-2">Top Assist Zones</h4>
              <div className="space-y-1">
                {sortZonesByAssists(data.zones)
                  .filter((z) => z.playerAssists > 0)
                  .slice(0, 3)
                  .map((zone, index) => (
                    <div
                      key={zone.zoneName}
                      className="flex items-center justify-between text-xs py-1"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">{index + 1}.</span>
                        <span>{zone.zoneName}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="font-mono">{zone.playerAssists} assists</span>
                        <span className="font-mono text-muted-foreground">
                          ({formatAssistPct(zone.playerAstPct)})
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Help text */}
          <p className="text-xs text-center text-muted-foreground">
            Hover over zones to see assist distribution and defensive rankings
          </p>
        </div>
      )}
    </div>
  );
}

export default AssistZonesCard;
