'use client';

import { useState } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  getDefensiveRankColor,
  getAssistHeatColor,
  getDefensiveRankTextClass,
  getDefensiveRankLabel,
  formatAssistCount,
  formatDefFgPct,
} from '@/lib/assist-zones';
import { ApiAssistZoneMatchup } from '@/lib/api';

interface AssistZonesCourtProps {
  zoneData: ApiAssistZoneMatchup[];
  totalAssists: number;
  className?: string;
}

// Court dimensions
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

export function AssistZonesCourt({
  zoneData,
  totalAssists,
  className = '',
}: AssistZonesCourtProps) {
  const [hoveredZone, setHoveredZone] = useState<string | null>(null);

  // Get zone data by name
  const getZone = (name: string): ApiAssistZoneMatchup | undefined => {
    return zoneData.find((z) => z.zoneName === name);
  };

  // Render a zone tooltip
  const ZoneTooltipContent = ({ zone }: { zone: ApiAssistZoneMatchup }) => {
    // Debug: log the zone data
    console.log('Zone data:', zone);

    return (
      <div className="p-3 space-y-2 min-w-[220px]">
        <div className="border-b pb-2 mb-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
          <div className="text-[10px] uppercase tracking-wider opacity-60" style={{ color: '#888' }}>
            Zone
          </div>
          <div className="font-semibold text-sm mt-1" style={{ color: '#fff' }}>
            {zone.zoneName || 'Unknown Zone'}
          </div>
        </div>
        {zone.hasData ? (
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span style={{ color: '#888' }}>Player Assists:</span>
              <span className="font-mono font-semibold" style={{ color: '#fff' }}>
                {zone.playerAssists} of {totalAssists} ({zone.playerAstPct?.toFixed(1)}%)
              </span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span style={{ color: '#888' }}>Opp DEF Rank:</span>
              <span className="font-mono font-semibold" style={{ color: zone.oppDefRank >= 21 ? '#4ade80' : zone.oppDefRank >= 11 ? '#facc15' : '#f87171' }}>
                #{zone.oppDefRank} of 30
              </span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span style={{ color: '#888' }}>Opp DEF FG%:</span>
              <span className="font-mono" style={{ color: '#fff' }}>
                {((zone.oppDefFgPct || 0) * 100).toFixed(1)}%
              </span>
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
    zone: ApiAssistZoneMatchup | undefined;
    children: React.ReactNode;
  }) => {
    if (!zone) return <>{children}</>;

    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <g
            className="cursor-pointer transition-opacity duration-150"
            style={{ opacity: hoveredZone === zone.zoneName ? 1 : 0.85 }}
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

  return (
    <TooltipProvider>
      <svg
        viewBox={`0 0 ${COURT_WIDTH} ${COURT_HEIGHT}`}
        className={`w-full max-w-[400px] mx-auto ${className}`}
        style={{ backgroundColor: 'oklch(0.15 0.005 285)' }}
      >
        {/* === ZONE LAYERS (bottom to top) === */}

        {/* Above the Break 3 - large arc area at bottom */}
        <InteractiveZone zone={getZone('Above the Break 3')}>
          <path
            d={`M 0 ${CORNER_3_HEIGHT}
                L 0 ${COURT_HEIGHT}
                L ${COURT_WIDTH} ${COURT_HEIGHT}
                L ${COURT_WIDTH} ${CORNER_3_HEIGHT}
                L ${COURT_WIDTH - CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 1 ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                Z`}
            fill={getAssistHeatColor(
              getZone('Above the Break 3')?.playerAstPct ?? 0,
              getZone('Above the Break 3')?.hasData ?? false
            )}
            stroke={getDefensiveRankColor(
              getZone('Above the Break 3')?.oppDefRank ?? 0,
              getZone('Above the Break 3')?.hasData ?? false
            )}
            strokeWidth="3"
          />
        </InteractiveZone>

        {/* Left Corner 3 - rectangle at top-left */}
        <InteractiveZone zone={getZone('Left Corner 3')}>
          <rect
            x="0"
            y="0"
            width={CORNER_3_WIDTH}
            height={CORNER_3_HEIGHT}
            fill={getAssistHeatColor(
              getZone('Left Corner 3')?.playerAstPct ?? 0,
              getZone('Left Corner 3')?.hasData ?? false
            )}
            stroke={getDefensiveRankColor(
              getZone('Left Corner 3')?.oppDefRank ?? 0,
              getZone('Left Corner 3')?.hasData ?? false
            )}
            strokeWidth="3"
          />
        </InteractiveZone>

        {/* Right Corner 3 - rectangle at top-right */}
        <InteractiveZone zone={getZone('Right Corner 3')}>
          <rect
            x={COURT_WIDTH - CORNER_3_WIDTH}
            y="0"
            width={CORNER_3_WIDTH}
            height={CORNER_3_HEIGHT}
            fill={getAssistHeatColor(
              getZone('Right Corner 3')?.playerAstPct ?? 0,
              getZone('Right Corner 3')?.hasData ?? false
            )}
            stroke={getDefensiveRankColor(
              getZone('Right Corner 3')?.oppDefRank ?? 0,
              getZone('Right Corner 3')?.hasData ?? false
            )}
            strokeWidth="3"
          />
        </InteractiveZone>

        {/* Mid-Range - area between paint and 3pt line */}
        {/* This fills the entire area inside the 3pt arc; Paint zone drawn later will cover the center */}
        <InteractiveZone zone={getZone('Mid-Range')}>
          <path
            d={`M ${CORNER_3_WIDTH} 0
                L ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 0 ${COURT_WIDTH - CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                L ${COURT_WIDTH - CORNER_3_WIDTH} 0
                Z`}
            fill={getAssistHeatColor(
              getZone('Mid-Range')?.playerAstPct ?? 0,
              getZone('Mid-Range')?.hasData ?? false
            )}
            stroke="none"
          />
        </InteractiveZone>

        {/* Paint (Non-RA) - key/paint area minus restricted area */}
        <InteractiveZone zone={getZone('In The Paint (Non-RA)')}>
          <path
            d={`M ${KEY_LEFT} 0
                L ${KEY_LEFT} ${KEY_HEIGHT}
                L ${KEY_RIGHT} ${KEY_HEIGHT}
                L ${KEY_RIGHT} 0
                Z`}
            fill={getAssistHeatColor(
              getZone('In The Paint (Non-RA)')?.playerAstPct ?? 0,
              getZone('In The Paint (Non-RA)')?.hasData ?? false
            )}
            stroke={getDefensiveRankColor(
              getZone('In The Paint (Non-RA)')?.oppDefRank ?? 0,
              getZone('In The Paint (Non-RA)')?.hasData ?? false
            )}
            strokeWidth="3"
          />
        </InteractiveZone>

        {/* Restricted Area - circle around basket */}
        <InteractiveZone zone={getZone('Restricted Area')}>
          <circle
            cx={BASKET_X}
            cy={BASKET_Y}
            r={RESTRICTED_RADIUS}
            fill={getAssistHeatColor(
              getZone('Restricted Area')?.playerAstPct ?? 0,
              getZone('Restricted Area')?.hasData ?? false
            )}
            stroke={getDefensiveRankColor(
              getZone('Restricted Area')?.oppDefRank ?? 0,
              getZone('Restricted Area')?.hasData ?? false
            )}
            strokeWidth="3"
          />
        </InteractiveZone>

        {/* === COURT LINES (for reference, subtle) === */}
        <g stroke="oklch(0.35 0.01 285)" strokeWidth="1.5" fill="none" opacity="0.3">
          {/* Basket */}
          <circle cx={BASKET_X} cy={BASKET_Y} r="7.5" />

          {/* Free throw line */}
          <line x1={KEY_LEFT} y1={KEY_HEIGHT} x2={KEY_RIGHT} y2={KEY_HEIGHT} />

          {/* Key/Paint outline */}
          <rect x={KEY_LEFT} y="0" width={KEY_WIDTH} height={KEY_HEIGHT} />

          {/* Three-point line */}
          <path
            d={`M ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 1 ${COURT_WIDTH - CORNER_3_WIDTH} ${CORNER_3_HEIGHT}`}
          />
          <line x1={CORNER_3_WIDTH} y1="0" x2={CORNER_3_WIDTH} y2={CORNER_3_HEIGHT} />
          <line x1={COURT_WIDTH - CORNER_3_WIDTH} y1="0" x2={COURT_WIDTH - CORNER_3_WIDTH} y2={CORNER_3_HEIGHT} />

          {/* Restricted area arc */}
          <path
            d={`M ${BASKET_X - RESTRICTED_RADIUS} ${BASKET_Y}
                A ${RESTRICTED_RADIUS} ${RESTRICTED_RADIUS} 0 0 1 ${BASKET_X + RESTRICTED_RADIUS} ${BASKET_Y}`}
          />
        </g>
      </svg>
    </TooltipProvider>
  );
}
