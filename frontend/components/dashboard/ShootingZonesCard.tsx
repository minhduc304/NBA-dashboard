'use client';

import { useEffect, useState, useCallback } from 'react';
import { Loader2 } from 'lucide-react';
import { BasketballCourt } from './BasketballCourt';
import { ErrorState } from '@/components/ui/error-state';
import {
  fetchShootingZoneMatchup,
  ApiShootingZoneMatchupResponse,
} from '@/lib/api';

interface ShootingZonesCardProps {
  playerId: number;
  opponentId: number;
  opponentName: string;
}

export function ShootingZonesCard({
  playerId,
  opponentId,
  opponentName,
}: ShootingZonesCardProps) {
  const [matchupData, setMatchupData] = useState<ApiShootingZoneMatchupResponse | null>(null);
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
        // Fetch combined matchup data with league context
        const data = await fetchShootingZoneMatchup(playerId, opponentId);
        setMatchupData(data);
      } catch (err) {
        console.error('Error fetching shooting zones:', err);
        setError('Unable to load shooting zone data');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [playerId, opponentId, retryCount]);

  // Check if we have any data
  const hasData = matchupData?.zones.some((z) => z.hasData) ?? false;

  return (
    <div className="card-surface rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-sm font-semibold text-foreground">Shooting Zones</h3>
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
          No shooting zone data available
        </div>
      ) : (
        <div className="space-y-4">
          {/* Basketball Court Visualization */}
          <BasketballCourt zoneData={matchupData!.zones} totalFga={matchupData!.totalFga} />

          {/* Color Legend */}
          <div className="flex items-center justify-center gap-3 pt-2">
            <div className="flex items-center gap-6 text-xs">
              <div className="flex items-center gap-1.5">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: 'var(--destructive)' }}
                />
                <span className="text-muted-foreground">Below Avg</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: 'var(--accent)' }}
                />
                <span className="text-muted-foreground">League Avg</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: 'var(--success)' }}
                />
                <span className="text-muted-foreground">Above Avg</span>
              </div>
            </div>
          </div>

          {/* Opacity Legend */}
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <span className="opacity-40">○</span>
            <span>Low volume</span>
            <span className="mx-2">→</span>
            <span>High volume</span>
            <span className="opacity-100">●</span>
          </div>

          {/* Help text */}
          <p className="text-xs text-center text-muted-foreground">
            Color = matchup quality • Opacity = shot volume
          </p>
        </div>
      )}
    </div>
  );
}

export default ShootingZonesCard;
