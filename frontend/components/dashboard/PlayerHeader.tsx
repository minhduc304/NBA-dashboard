'use client';

import { useState, useEffect } from 'react';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { NBA_TEAMS, type Player } from '@/lib/data';
import { type ApiPropLine } from '@/lib/api';
import { formatOdds } from '@/lib/constants';

interface PlayerHeaderProps {
  player: Player;
  seasonAvg: number | null;
  graphAvg: number | null;
  hitRate: number;
  hitRateFraction: string;
  currentProp: ApiPropLine | null;
  isLoadingStats: boolean;
  isLoadingProps: boolean;
}

export function PlayerHeader({
  player,
  seasonAvg,
  graphAvg,
  hitRate,
  hitRateFraction,
  currentProp,
  isLoadingStats,
  isLoadingProps,
}: PlayerHeaderProps) {
  // Track headshot image loading state
  const [imageError, setImageError] = useState(false);
  const headshotSrc = `/assets/${player.id}.png`;

  // Reset image error state when player changes
  useEffect(() => {
    setImageError(false);
  }, [player.id]);

  const teamData = NBA_TEAMS[player.team as keyof typeof NBA_TEAMS];
  const primaryColor = teamData?.color || '#6366f1';
  const secondaryColor = teamData?.colorSecondary || '#8b5cf6';

  return (
    <div className="flex flex-col lg:flex-row items-start justify-between gap-4 lg:gap-8 p-4 lg:p-6 rounded-xl bg-card border border-border">
      {/* Left: Player Info */}
      <div className="flex items-start gap-4">
        {/* Avatar / Headshot with team color gradient outline */}
        <div className="relative">
          <div
            className="w-[72px] h-[72px] lg:w-[88px] lg:h-[88px] rounded-full p-1 flex items-center justify-center"
            style={{
              background: `linear-gradient(135deg, ${primaryColor}, ${secondaryColor})`,
            }}
          >
            <div className="w-16 h-16 lg:w-20 lg:h-20 rounded-full bg-card flex items-center justify-center overflow-hidden">
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
                <span className="text-xl lg:text-2xl font-bold text-foreground">
                  {player.name.split(' ').map(n => n[0]).join('')}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Name & Badges */}
        <div className="space-y-2">
          <div>
            <h2 className="text-lg lg:text-xl font-semibold">{player.name}</h2>
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
      <div className="flex gap-4 lg:gap-8 w-full lg:w-auto justify-around lg:justify-start">
        <div className="text-center">
          <div className="text-xs font-semibold text-muted-foreground tracking-wider uppercase mb-1">
            SZN AVG
          </div>
          <div className={cn(
            "text-2xl lg:text-3xl font-bold font-mono transition-colors duration-200",
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
            "text-2xl lg:text-3xl font-bold font-mono transition-colors duration-200",
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
            "text-2xl lg:text-3xl font-bold font-mono transition-colors duration-200",
            hitRate < 50 ? "text-red-500" : "text-green-500"
          )}>
            {hitRate}%
            <span className="text-xs lg:text-sm text-muted-foreground ml-1">
              [{hitRateFraction}]
            </span>
          </div>
        </div>
      </div>

      {/* Right: Current Stat Prop Line */}
      <div className="flex items-center gap-3 p-3 lg:p-4 rounded-xl bg-secondary/50 border border-border w-full lg:w-auto justify-center lg:justify-start">
        {isLoadingProps ? (
          <div className="text-sm text-muted-foreground">Loading...</div>
        ) : currentProp ? (
          <>
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Line</div>
              <div className="text-xl font-bold font-mono">{currentProp.line}</div>
            </div>
            <div className="flex gap-2">
              <div className="px-3 py-2 rounded-lg bg-green-500/20 text-green-500 font-semibold text-sm">
                O {formatOdds(currentProp.overOdds)}
              </div>
              <div className="px-3 py-2 rounded-lg bg-red-500/20 text-red-500 font-semibold text-sm">
                U {formatOdds(currentProp.underOdds)}
              </div>
            </div>
          </>
        ) : (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertCircle className="w-4 h-4" />
            <span>No line available</span>
          </div>
        )}
      </div>
    </div>
  );
}
