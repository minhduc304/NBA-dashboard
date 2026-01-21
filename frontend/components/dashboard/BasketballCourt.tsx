'use client';

import { useState } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ApiShootingZoneMatchup } from '@/lib/api';

// Zone display names (shorter versions for UI)
const ZONE_DISPLAY_NAMES: Record<string, string> = {
  'Restricted Area': 'Restricted Area',
  'In The Paint (Non-RA)': 'Paint',
  'Mid-Range': 'Mid-Range',
  'Left Corner 3': 'Left Corner 3',
  'Right Corner 3': 'Right Corner 3',
  'Above the Break 3': 'Above Break 3',
};

interface BasketballCourtProps {
  zoneData: ApiShootingZoneMatchup[];
  totalFga: number;
  className?: string;
}

// Court dimensions matching the reference image layout
const COURT_WIDTH = 500;
const COURT_HEIGHT = 380;

// Basket position (at top center)
const BASKET_X = COURT_WIDTH / 2;
const BASKET_Y = 35;

// Paint/Key dimensions
const KEY_WIDTH = 150;
const KEY_HEIGHT = 140;
const KEY_LEFT = BASKET_X - KEY_WIDTH / 2;
const KEY_RIGHT = BASKET_X + KEY_WIDTH / 2;

// Restricted area (semi-circle under basket)
const RESTRICTED_RADIUS = 35;

// Three-point line
const CORNER_3_WIDTH = 55;
const CORNER_3_HEIGHT = 90;
const THREE_PT_RADIUS = 180;

// OKLCH color values
const COLORS = {
  red: { l: 0.60, c: 0.22, h: 25 },      // Unfavorable
  yellow: { l: 0.80, c: 0.18, h: 85 },   // Neutral
  green: { l: 0.65, c: 0.20, h: 145 },   // Favorable
  neutral: { l: 0.25, c: 0.01, h: 285 }, // No data
};

function interpolateOklch(
  from: { l: number; c: number; h: number },
  to: { l: number; c: number; h: number },
  t: number
): { l: number; c: number; h: number } {
  return {
    l: from.l + (to.l - from.l) * t,
    c: from.c + (to.c - from.c) * t,
    h: from.h + (to.h - from.h) * t,
  };
}

/**
 * Get zone fill color based on league-adjusted advantage
 * Advantage ranges from roughly -15% to +15%
 */
function getZoneColor(advantage: number, hasData: boolean): { l: number; c: number; h: number } {
  if (!hasData) {
    return COLORS.neutral;
  }

  // Clamp and normalize: -15% = 0, 0% = 0.5, +15% = 1
  const normalized = Math.max(0, Math.min(1, (advantage + 15) / 30));

  if (normalized < 0.5) {
    return interpolateOklch(COLORS.red, COLORS.yellow, normalized * 2);
  } else {
    return interpolateOklch(COLORS.yellow, COLORS.green, (normalized - 0.5) * 2);
  }
}

/**
 * Calculate opacity based on volume percentage
 * High volume = solid, low volume = faded
 */
function getVolumeOpacity(volumePct: number, hasData: boolean): number {
  if (!hasData) return 0.3;
  // Volume typically ranges from 1% to 40%
  // Map to opacity range 0.35 to 1.0
  const normalized = Math.min(volumePct / 35, 1); // Cap at 35% for full opacity
  return 0.35 + normalized * 0.65;
}

/**
 * Format opponent rank with ordinal suffix
 */
function formatRank(rank: number): string {
  if (rank === 1) return '1st';
  if (rank === 2) return '2nd';
  if (rank === 3) return '3rd';
  return `${rank}th`;
}

/**
 * Get defense quality label
 */
function getDefenseLabel(rank: number): { label: string; color: string } {
  if (rank <= 5) return { label: 'Elite', color: '#f87171' }; // Red = hard for player
  if (rank <= 10) return { label: 'Good', color: '#fb923c' };
  if (rank <= 20) return { label: 'Average', color: '#facc15' };
  if (rank <= 25) return { label: 'Weak', color: '#a3e635' };
  return { label: 'Poor', color: '#4ade80' }; // Green = easy for player
}

export function BasketballCourt({ zoneData, totalFga, className = '' }: BasketballCourtProps) {
  const [hoveredZone, setHoveredZone] = useState<string | null>(null);

  // Get zone data by name
  const getZone = (name: string): ApiShootingZoneMatchup | undefined => {
    return zoneData.find((z) => z.zoneName === name);
  };

  // Render enriched tooltip
  const ZoneTooltipContent = ({ zone }: { zone: ApiShootingZoneMatchup }) => {
    const defenseInfo = getDefenseLabel(zone.oppRank);

    return (
      <div className="p-3 space-y-2 min-w-[240px]">
        {/* Zone Header */}
        <div className="border-b pb-2 mb-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
          <div className="font-semibold text-sm" style={{ color: '#fff' }}>
            {ZONE_DISPLAY_NAMES[zone.zoneName] || zone.zoneName}
          </div>
          <div className="text-[10px] mt-1" style={{ color: '#888' }}>
            {zone.isThree ? '3-Point Zone' : '2-Point Zone'}
          </div>
        </div>

        {zone.hasData ? (
          <div className="space-y-3">
            {/* Player Stats */}
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: '#666' }}>
                Player
              </div>
              <div className="flex justify-between items-center text-xs">
                <span style={{ color: '#888' }}>FG%:</span>
                <span className="font-mono font-semibold" style={{ color: '#fff' }}>
                  {zone.playerFgPct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span style={{ color: '#888' }}>Attempts:</span>
                <span className="font-mono" style={{ color: '#fff' }}>
                  {zone.playerFgm.toFixed(0)}/{zone.playerFga.toFixed(0)} ({zone.playerVolumePct.toFixed(0)}% of shots)
                </span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span style={{ color: '#888' }}>vs League Avg:</span>
                <span
                  className="font-mono font-semibold"
                  style={{ color: zone.playerFgPct > zone.leagueAvgPct ? '#4ade80' : zone.playerFgPct < zone.leagueAvgPct - 3 ? '#f87171' : '#facc15' }}
                >
                  {zone.playerFgPct > zone.leagueAvgPct ? '+' : ''}{(zone.playerFgPct - zone.leagueAvgPct).toFixed(1)}%
                </span>
              </div>
            </div>

            {/* Opponent Defense */}
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: '#666' }}>
                Opponent Defense
              </div>
              <div className="flex justify-between items-center text-xs">
                <span style={{ color: '#888' }}>Allows:</span>
                <span className="font-mono" style={{ color: '#fff' }}>
                  {zone.oppFgPct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span style={{ color: '#888' }}>Rank:</span>
                <span className="font-mono" style={{ color: defenseInfo.color }}>
                  {formatRank(zone.oppRank)} ({defenseInfo.label})
                </span>
              </div>
            </div>

            {/* League Context */}
            <div className="pt-2 border-t" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
              <div className="flex justify-between items-center text-xs">
                <span style={{ color: '#888' }}>League Avg:</span>
                <span className="font-mono" style={{ color: '#888' }}>
                  {zone.leagueAvgPct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center text-xs mt-1">
                <span style={{ color: '#888' }}>Matchup Adv:</span>
                <span
                  className="font-mono font-bold"
                  style={{ color: zone.advantage > 5 ? '#4ade80' : zone.advantage > -5 ? '#facc15' : '#f87171' }}
                >
                  {zone.advantage > 0 ? '+' : ''}{zone.advantage.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs italic" style={{ color: '#888' }}>No data available</div>
        )}
      </div>
    );
  };

  // Interactive zone wrapper
  const InteractiveZone = ({
    zone,
    children,
  }: {
    zone: ApiShootingZoneMatchup | undefined;
    children: React.ReactNode;
  }) => {
    if (!zone) return <>{children}</>;

    const baseOpacity = getVolumeOpacity(zone.playerVolumePct, zone.hasData);
    const hoverOpacity = Math.min(baseOpacity + 0.15, 1);

    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <g
            className="cursor-pointer transition-opacity duration-150"
            style={{ opacity: hoveredZone === zone.zoneName ? hoverOpacity : baseOpacity }}
            onMouseEnter={() => setHoveredZone(zone.zoneName)}
            onMouseLeave={() => setHoveredZone(null)}
          >
            {children}
          </g>
        </TooltipTrigger>
        <TooltipContent side="top" className="bg-card border-border">
          <ZoneTooltipContent zone={zone} />
        </TooltipContent>
      </Tooltip>
    );
  };

  // Helper to get fill color string
  const getFillColor = (zoneName: string): string => {
    const zone = getZone(zoneName);
    const color = getZoneColor(zone?.advantage ?? 0, zone?.hasData ?? false);
    return `oklch(${color.l.toFixed(3)} ${color.c.toFixed(3)} ${color.h.toFixed(1)})`;
  };

  return (
    <TooltipProvider>
      <svg
        viewBox={`0 0 ${COURT_WIDTH} ${COURT_HEIGHT}`}
        className={`w-full max-w-[400px] mx-auto ${className}`}
        style={{ backgroundColor: 'oklch(0.15 0.005 285)' }}
      >
        {/* === ZONE LAYERS (bottom to top) === */}

        {/* Above the Break 3 */}
        <InteractiveZone zone={getZone('Above the Break 3')}>
          <path
            d={`M 0 ${CORNER_3_HEIGHT}
                L 0 ${COURT_HEIGHT}
                L ${COURT_WIDTH} ${COURT_HEIGHT}
                L ${COURT_WIDTH} ${CORNER_3_HEIGHT}
                L ${COURT_WIDTH - CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 0 ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                Z`}
            fill={getFillColor('Above the Break 3')}
          />
        </InteractiveZone>

        {/* Left Corner 3 */}
        <InteractiveZone zone={getZone('Left Corner 3')}>
          <rect
            x="0"
            y="0"
            width={CORNER_3_WIDTH}
            height={CORNER_3_HEIGHT}
            fill={getFillColor('Left Corner 3')}
          />
        </InteractiveZone>

        {/* Right Corner 3 */}
        <InteractiveZone zone={getZone('Right Corner 3')}>
          <rect
            x={COURT_WIDTH - CORNER_3_WIDTH}
            y="0"
            width={CORNER_3_WIDTH}
            height={CORNER_3_HEIGHT}
            fill={getFillColor('Right Corner 3')}
          />
        </InteractiveZone>

        {/* Mid-Range */}
        <InteractiveZone zone={getZone('Mid-Range')}>
          <path
            d={`M ${CORNER_3_WIDTH} 0
                L ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 0 ${COURT_WIDTH - CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                L ${COURT_WIDTH - CORNER_3_WIDTH} 0
                Z`}
            fill={getFillColor('Mid-Range')}
          />
        </InteractiveZone>

        {/* Paint (Non-RA) */}
        <InteractiveZone zone={getZone('In The Paint (Non-RA)')}>
          <path
            d={`M ${KEY_LEFT} 0
                L ${KEY_LEFT} ${KEY_HEIGHT}
                L ${KEY_RIGHT} ${KEY_HEIGHT}
                L ${KEY_RIGHT} 0
                Z`}
            fill={getFillColor('In The Paint (Non-RA)')}
          />
        </InteractiveZone>

        {/* Restricted Area */}
        <InteractiveZone zone={getZone('Restricted Area')}>
          <circle
            cx={BASKET_X}
            cy={BASKET_Y}
            r={RESTRICTED_RADIUS}
            fill={getFillColor('Restricted Area')}
          />
        </InteractiveZone>

        {/* === COURT LINES === */}
        <rect
          x="0" y="0"
          width={COURT_WIDTH} height={COURT_HEIGHT}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        <path
          d={`M ${CORNER_3_WIDTH} 0
              L ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
              A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 0 ${COURT_WIDTH - CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
              L ${COURT_WIDTH - CORNER_3_WIDTH} 0`}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        <rect
          x={KEY_LEFT} y="0"
          width={KEY_WIDTH} height={KEY_HEIGHT}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        <path
          d={`M ${BASKET_X - RESTRICTED_RADIUS} ${BASKET_Y}
              A ${RESTRICTED_RADIUS} ${RESTRICTED_RADIUS} 0 0 0 ${BASKET_X + RESTRICTED_RADIUS} ${BASKET_Y}`}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        <path
          d={`M ${BASKET_X - 55} ${KEY_HEIGHT}
              A 55 55 0 0 1 ${BASKET_X + 55} ${KEY_HEIGHT}`}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        {/* Basket */}
        <circle
          cx={BASKET_X}
          cy={BASKET_Y - 10}
          r="7"
          fill="none"
          stroke="oklch(0.55 0.12 25)"
          strokeWidth="2.5"
        />

        {/* Backboard */}
        <line
          x1={BASKET_X - 25} y1="8"
          x2={BASKET_X + 25} y2="8"
          stroke="oklch(0.45 0.005 285)"
          strokeWidth="3"
        />
      </svg>
    </TooltipProvider>
  );
}

export default BasketballCourt;
