'use client';

import { useState } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  ShootingZoneMatchup,
  getZoneColor,
  getAdvantageTextColor,
  formatAdvantage,
  ZONE_DISPLAY_NAMES,
  ZoneName,
} from '@/lib/shooting-zones';

interface BasketballCourtProps {
  zoneData: ShootingZoneMatchup[];
  className?: string;
}

// Court dimensions matching the reference image layout
// Basket at top, 3pt arc curving downward toward bottom
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
const CORNER_3_WIDTH = 55; // Width of corner 3 zones
const CORNER_3_HEIGHT = 90; // Height where corner meets arc
const THREE_PT_RADIUS = 180; // Arc radius

export function BasketballCourt({ zoneData, className = '' }: BasketballCourtProps) {
  const [hoveredZone, setHoveredZone] = useState<ZoneName | null>(null);

  // Get zone data by name
  const getZone = (name: ZoneName): ShootingZoneMatchup | undefined => {
    return zoneData.find((z) => z.zoneName === name);
  };

  // Render a zone tooltip
  const ZoneTooltipContent = ({ zone }: { zone: ShootingZoneMatchup }) => (
    <div className="p-2 space-y-2 min-w-[200px]">
      <div className="border-b border-border pb-2">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Zone</div>
        <div className="font-semibold text-sm">
          {ZONE_DISPLAY_NAMES[zone.zoneName]}
        </div>
      </div>
      {zone.hasData ? (
        <>
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Player FG%</span>
            <span className="font-mono">
              {zone.playerFgPct.toFixed(1)}%
              <span className="text-muted-foreground ml-1">
                ({zone.playerFgm.toFixed(1)}/{zone.playerFga.toFixed(1)})
              </span>
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Opp DEF FG%</span>
            <span className="font-mono">{zone.oppDefFgPct.toFixed(1)}%</span>
          </div>
          <div className="flex justify-between text-xs pt-1 border-t border-border">
            <span className="text-muted-foreground">Advantage</span>
            <span className={`font-mono font-semibold ${getAdvantageTextColor(zone.advantage)}`}>
              {formatAdvantage(zone.advantage)}
            </span>
          </div>
        </>
      ) : (
        <div className="text-xs text-muted-foreground italic">No data available</div>
      )}
    </div>
  );

  // Interactive zone wrapper
  const InteractiveZone = ({
    zone,
    children,
  }: {
    zone: ShootingZoneMatchup | undefined;
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
                A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 0 ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                Z`}
            fill={getZoneColor(
              getZone('Above the Break 3')?.advantage ?? 0,
              getZone('Above the Break 3')?.hasData ?? false
            )}
          />
        </InteractiveZone>

        {/* Left Corner 3 - rectangle at top-left */}
        <InteractiveZone zone={getZone('Left Corner 3')}>
          <rect
            x="0"
            y="0"
            width={CORNER_3_WIDTH}
            height={CORNER_3_HEIGHT}
            fill={getZoneColor(
              getZone('Left Corner 3')?.advantage ?? 0,
              getZone('Left Corner 3')?.hasData ?? false
            )}
          />
        </InteractiveZone>

        {/* Right Corner 3 - rectangle at top-right */}
        <InteractiveZone zone={getZone('Right Corner 3')}>
          <rect
            x={COURT_WIDTH - CORNER_3_WIDTH}
            y="0"
            width={CORNER_3_WIDTH}
            height={CORNER_3_HEIGHT}
            fill={getZoneColor(
              getZone('Right Corner 3')?.advantage ?? 0,
              getZone('Right Corner 3')?.hasData ?? false
            )}
          />
        </InteractiveZone>

        {/* Mid-Range - area inside 3pt arc but outside paint */}
        <InteractiveZone zone={getZone('Mid-Range')}>
          <path
            d={`M ${CORNER_3_WIDTH} 0
                L ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 1 ${COURT_WIDTH - CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
                L ${COURT_WIDTH - CORNER_3_WIDTH} 0
                L ${KEY_RIGHT} 0
                L ${KEY_RIGHT} ${KEY_HEIGHT}
                L ${KEY_LEFT} ${KEY_HEIGHT}
                L ${KEY_LEFT} 0
                Z`}
            fill={getZoneColor(
              getZone('Mid-Range')?.advantage ?? 0,
              getZone('Mid-Range')?.hasData ?? false
            )}
            fillRule="evenodd"
          />
        </InteractiveZone>

        {/* Paint (Non-RA) - rectangle from baseline, excluding restricted area */}
        <InteractiveZone zone={getZone('In The Paint (Non-RA)')}>
          <path
            d={`M ${KEY_LEFT} 0
                L ${KEY_LEFT} ${KEY_HEIGHT}
                L ${KEY_RIGHT} ${KEY_HEIGHT}
                L ${KEY_RIGHT} 0
                Z
                M ${BASKET_X - RESTRICTED_RADIUS} ${BASKET_Y}
                A ${RESTRICTED_RADIUS} ${RESTRICTED_RADIUS} 0 0 1 ${BASKET_X + RESTRICTED_RADIUS} ${BASKET_Y}
                L ${BASKET_X + RESTRICTED_RADIUS} 0
                L ${BASKET_X - RESTRICTED_RADIUS} 0
                Z`}
            fill={getZoneColor(
              getZone('In The Paint (Non-RA)')?.advantage ?? 0,
              getZone('In The Paint (Non-RA)')?.hasData ?? false
            )}
            fillRule="evenodd"
          />
        </InteractiveZone>

        {/* Restricted Area - semi-circle under basket */}
        <InteractiveZone zone={getZone('Restricted Area')}>
          <path
            d={`M ${BASKET_X - RESTRICTED_RADIUS} 0
                L ${BASKET_X - RESTRICTED_RADIUS} ${BASKET_Y}
                A ${RESTRICTED_RADIUS} ${RESTRICTED_RADIUS} 0 0 0 ${BASKET_X + RESTRICTED_RADIUS} ${BASKET_Y}
                L ${BASKET_X + RESTRICTED_RADIUS} 0
                Z`}
            fill={getZoneColor(
              getZone('Restricted Area')?.advantage ?? 0,
              getZone('Restricted Area')?.hasData ?? false
            )}
          />
        </InteractiveZone>

        {/* === COURT LINES (on top of zones) === */}

        {/* Court outline */}
        <rect
          x="0"
          y="0"
          width={COURT_WIDTH}
          height={COURT_HEIGHT}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        {/* Three-point line */}
        <path
          d={`M ${CORNER_3_WIDTH} 0
              L ${CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
              A ${THREE_PT_RADIUS} ${THREE_PT_RADIUS} 0 0 0 ${COURT_WIDTH - CORNER_3_WIDTH} ${CORNER_3_HEIGHT}
              L ${COURT_WIDTH - CORNER_3_WIDTH} 0`}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        {/* Paint/Key rectangle */}
        <rect
          x={KEY_LEFT}
          y="0"
          width={KEY_WIDTH}
          height={KEY_HEIGHT}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        {/* Restricted area semi-circle */}
        <path
          d={`M ${BASKET_X - RESTRICTED_RADIUS} ${BASKET_Y}
              A ${RESTRICTED_RADIUS} ${RESTRICTED_RADIUS} 0 0 0 ${BASKET_X + RESTRICTED_RADIUS} ${BASKET_Y}`}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        {/* Free throw circle (bottom half) */}
        <path
          d={`M ${BASKET_X - 55} ${KEY_HEIGHT}
              A 55 55 0 0 1 ${BASKET_X + 55} ${KEY_HEIGHT}`}
          fill="none"
          stroke="oklch(0.35 0.005 285)"
          strokeWidth="2"
        />

        {/* Basket/Rim */}
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
          x1={BASKET_X - 25}
          y1="8"
          x2={BASKET_X + 25}
          y2="8"
          stroke="oklch(0.45 0.005 285)"
          strokeWidth="3"
        />
      </svg>
    </TooltipProvider>
  );
}

export default BasketballCourt;
