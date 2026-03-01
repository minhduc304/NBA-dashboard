'use client';

import { useState, useEffect } from 'react';
import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { type Player } from '@/lib/data';
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
  const [imageError, setImageError] = useState(false);
  const headshotSrc = `/assets/${player.id}.png`;

  useEffect(() => {
    setImageError(false);
  }, [player.id]);

  return (
    <div className="card-surface rounded-lg p-5">
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-5">
        {/* Left: Player Info */}
        <div className="flex items-center gap-4">
          {/* Avatar — supportive, not the focus */}
          <div className="w-16 h-16 lg:w-[72px] lg:h-[72px] rounded-full border border-border bg-card flex items-center justify-center overflow-hidden shrink-0">
            {!imageError ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={headshotSrc}
                alt={player.name}
                width={72}
                height={72}
                className="object-cover w-full h-full"
                onError={() => setImageError(true)}
              />
            ) : (
              <span className="font-mono text-lg text-muted-foreground">
                {player.name.split(' ').map(n => n[0]).join('')}
              </span>
            )}
          </div>

          {/* Name & Position */}
          <div>
            <h2 className="font-display text-lg lg:text-xl font-bold text-foreground">{player.name}</h2>
            <p className="font-sans text-sm text-muted-foreground">{player.position}</p>
            {player.badges && player.badges.length > 0 && (
              <div className="flex gap-1.5 mt-1.5">
                {player.badges.map((badge) => (
                  <Badge key={badge} variant="neutral">
                    {badge}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Center: Stat Trio with vertical dividers */}
        <div className="flex items-stretch">
          {/* SZN AVG */}
          <div className="flex flex-col items-center justify-center px-4">
            <div className="label-meta mb-1">SZN AVG</div>
            <div className={cn(
              "stat-number text-2xl font-bold duration-150",
              isLoadingStats ? "text-muted-foreground" : "text-foreground"
            )}>
              {isLoadingStats ? '—' : (seasonAvg ?? '—')}
            </div>
          </div>

          <div className="w-px bg-border my-2" />

          {/* GRAPH AVG */}
          <div className="flex flex-col items-center justify-center px-4">
            <div className="label-meta mb-1">GRAPH AVG</div>
            <div className={cn(
              "stat-number text-2xl font-bold duration-150",
              isLoadingStats ? "text-muted-foreground" : "text-foreground"
            )}>
              {isLoadingStats ? '—' : (graphAvg ?? '—')}
            </div>
          </div>

          <div className="w-px bg-border my-2" />

          {/* HIT RATE — the most important number */}
          <div className="flex flex-col items-center justify-center px-4">
            <div className="label-meta mb-1">HIT RATE</div>
            <div className="flex items-baseline gap-1.5">
              <span className={cn(
                "stat-number text-3xl font-bold",
                hitRate >= 50 ? "text-success" : "text-destructive"
              )}>
                {hitRate}%
              </span>
              <span className="font-mono text-xs text-muted-foreground">
                [{hitRateFraction}]
              </span>
            </div>
          </div>
        </div>

        {/* Right: Line Box */}
        <div className="border border-border rounded-md p-3 min-w-[160px]">
          {isLoadingProps ? (
            <div className="text-sm text-muted-foreground">Loading...</div>
          ) : currentProp ? (
            <div className="space-y-2">
              <div className="label-meta">Line</div>
              <div className="stat-number text-2xl font-bold text-accent">
                {currentProp.line}
              </div>
              <div className="flex gap-2">
                <div className="px-2 py-1 rounded-sm bg-success/12 text-success font-mono text-xs font-semibold">
                  O {formatOdds(currentProp.overOdds)}
                </div>
                <div className="px-2 py-1 rounded-sm bg-destructive/12 text-destructive font-mono text-xs font-semibold">
                  U {formatOdds(currentProp.underOdds)}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <AlertCircle className="w-4 h-4" />
              <span>No line available</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
