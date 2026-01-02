'use client';

import Image from 'next/image';
import { cn } from '@/lib/utils';

// NBA Team ID mapping
const TEAM_IDS: Record<string, number> = {
  ATL: 1610612737,
  BOS: 1610612738,
  BKN: 1610612751,
  CHA: 1610612766,
  CHI: 1610612741,
  CLE: 1610612739,
  DAL: 1610612742,
  DEN: 1610612743,
  DET: 1610612765,
  GSW: 1610612744,
  HOU: 1610612745,
  IND: 1610612754,
  LAC: 1610612746,
  LAL: 1610612747,
  MEM: 1610612763,
  MIA: 1610612748,
  MIL: 1610612749,
  MIN: 1610612750,
  NOP: 1610612740,
  NYK: 1610612752,
  OKC: 1610612760,
  ORL: 1610612753,
  PHI: 1610612755,
  PHX: 1610612756,
  POR: 1610612757,
  SAC: 1610612758,
  SAS: 1610612759,
  TOR: 1610612761,
  UTA: 1610612762,
  WAS: 1610612764,
};

interface TeamLogoProps {
  team: string;
  size?: number;
  className?: string;
}

export function TeamLogo({ team, size = 40, className }: TeamLogoProps) {
  const teamId = TEAM_IDS[team.toUpperCase()];

  if (!teamId) {
    // Fallback to colored circle with abbreviation
    return (
      <div
        className={cn(
          "rounded-full bg-muted flex items-center justify-center font-bold text-xs",
          className
        )}
        style={{ width: size, height: size }}
      >
        {team.slice(0, 3).toUpperCase()}
      </div>
    );
  }

  // Use NBA CDN for logos
  const logoUrl = `https://cdn.nba.com/logos/nba/${teamId}/global/L/logo.svg`;

  return (
    <Image
      src={logoUrl}
      alt={`${team} logo`}
      width={size}
      height={size}
      className={cn("object-contain", className)}
      unoptimized // CDN images don't need Next.js optimization
    />
  );
}
