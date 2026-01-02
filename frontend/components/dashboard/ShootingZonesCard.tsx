'use client';

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { BasketballCourt } from './BasketballCourt';
import {
  fetchPlayerShootingZones,
  fetchTeamDefensiveZones,
} from '@/lib/api';
import {
  ShootingZoneMatchup,
  combineZoneData,
} from '@/lib/shooting-zones';

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
  const [zoneMatchups, setZoneMatchups] = useState<ShootingZoneMatchup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      if (!playerId || !opponentId) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        // Fetch both datasets in parallel
        const [playerZones, opponentZones] = await Promise.all([
          fetchPlayerShootingZones(playerId),
          fetchTeamDefensiveZones(opponentId),
        ]);

        // Combine the data
        const combined = combineZoneData(playerZones, opponentZones);
        setZoneMatchups(combined);
      } catch (err) {
        console.error('Error fetching shooting zones:', err);
        setError('Failed to load shooting zone data');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [playerId, opponentId]);

  // Check if we have any data
  const hasData = zoneMatchups.some((z) => z.hasData);

  return (
    <div className="p-6 rounded-xl bg-card border border-border">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Shooting Zones</h3>
        <span className="text-sm text-muted-foreground">vs {opponentName}</span>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading zones...</span>
        </div>
      ) : error ? (
        <div className="text-center py-8 text-sm text-muted-foreground">
          {error}
        </div>
      ) : !hasData ? (
        <div className="text-center py-8 text-sm text-muted-foreground">
          No shooting zone data available
        </div>
      ) : (
        <div className="space-y-4">
          {/* Basketball Court Visualization */}
          <BasketballCourt zoneData={zoneMatchups} />

          {/* Color Legend */}
          <div className="flex items-center justify-center gap-3 pt-2">
            <div className="flex items-center gap-6 text-xs">
              <div className="flex items-center gap-1.5">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: 'oklch(0.60 0.22 25)' }}
                />
                <span className="text-muted-foreground">Unfavorable</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: 'oklch(0.80 0.18 85)' }}
                />
                <span className="text-muted-foreground">Neutral</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: 'oklch(0.65 0.20 145)' }}
                />
                <span className="text-muted-foreground">Favorable</span>
              </div>
            </div>
          </div>

          {/* Help text */}
          <p className="text-xs text-center text-muted-foreground">
            Hover over zones to see FG% matchup details
          </p>
        </div>
      )}
    </div>
  );
}

export default ShootingZonesCard;
