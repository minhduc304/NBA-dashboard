/**
 * Shooting Zones Utilities
 * Types, color interpolation, and zone geometry for basketball court visualization
 */

import { ApiPlayerShootingZone, ApiTeamDefensiveZone } from './api';

// Zone names as stored in the database
export const ZONE_NAMES = [
  'Restricted Area',
  'In The Paint (Non-RA)',
  'Mid-Range',
  'Left Corner 3',
  'Right Corner 3',
  'Above the Break 3',
] as const;

export type ZoneName = typeof ZONE_NAMES[number];

// Combined matchup data for visualization
export interface ShootingZoneMatchup {
  zoneName: ZoneName;
  playerFgPct: number;
  playerFga: number;
  playerFgm: number;
  oppDefFgPct: number;
  oppDefFga: number;
  advantage: number; // playerFgPct - oppDefFgPct (positive = favorable)
  hasData: boolean;
}

// OKLCH color values matching globals.css
const COLORS = {
  red: { l: 0.60, c: 0.22, h: 25 },      // Destructive - unfavorable
  yellow: { l: 0.80, c: 0.18, h: 85 },   // Accent - neutral
  green: { l: 0.65, c: 0.20, h: 145 },   // Success - favorable
  neutral: { l: 0.25, c: 0.01, h: 285 }, // No data - muted
};

/**
 * Interpolate between two OKLCH colors
 */
function interpolateOklch(
  from: { l: number; c: number; h: number },
  to: { l: number; c: number; h: number },
  t: number
): string {
  const l = from.l + (to.l - from.l) * t;
  const c = from.c + (to.c - from.c) * t;
  const h = from.h + (to.h - from.h) * t;
  return `oklch(${l.toFixed(3)} ${c.toFixed(3)} ${h.toFixed(1)})`;
}

/**
 * Get zone fill color based on matchup advantage
 * Advantage ranges from roughly -15% to +15%
 * -15% or worse = red, 0% = yellow, +15% or better = green
 */
export function getZoneColor(advantage: number, hasData: boolean = true): string {
  if (!hasData) {
    return interpolateOklch(COLORS.neutral, COLORS.neutral, 1);
  }

  // Clamp and normalize to 0-1 range
  // -15% = 0, 0% = 0.5, +15% = 1
  const normalized = Math.max(0, Math.min(1, (advantage + 15) / 30));

  if (normalized < 0.5) {
    // Red to Yellow (0-0.5 maps to red-yellow)
    const t = normalized * 2;
    return interpolateOklch(COLORS.red, COLORS.yellow, t);
  } else {
    // Yellow to Green (0.5-1 maps to yellow-green)
    const t = (normalized - 0.5) * 2;
    return interpolateOklch(COLORS.yellow, COLORS.green, t);
  }
}

/**
 * Get text color for advantage display
 */
export function getAdvantageTextColor(advantage: number): string {
  if (advantage > 3) return 'text-green-400';
  if (advantage < -3) return 'text-red-400';
  return 'text-yellow-400';
}

/**
 * Format advantage as a percentage string with sign
 */
export function formatAdvantage(advantage: number): string {
  const sign = advantage >= 0 ? '+' : '';
  return `${sign}${advantage.toFixed(1)}%`;
}

/**
 * Combine player shooting zones with opponent defensive zones
 */
export function combineZoneData(
  playerZones: ApiPlayerShootingZone[],
  opponentZones: ApiTeamDefensiveZone[]
): ShootingZoneMatchup[] {
  return ZONE_NAMES.map((zoneName) => {
    const playerZone = playerZones.find((z) => z.zone_name === zoneName);
    const oppZone = opponentZones.find((z) => z.zone_name === zoneName);

    const playerFgPct = playerZone?.fg_pct ?? 0;
    const oppDefFgPct = oppZone?.opp_fg_pct ?? 0;
    const hasData = !!playerZone && !!oppZone;

    return {
      zoneName,
      playerFgPct: playerFgPct * 100, // Convert to percentage
      playerFga: playerZone?.fga ?? 0,
      playerFgm: playerZone?.fgm ?? 0,
      oppDefFgPct: oppDefFgPct * 100, // Convert to percentage
      oppDefFga: oppZone?.opp_fga ?? 0,
      advantage: (playerFgPct - oppDefFgPct) * 100, // Difference in percentage points
      hasData,
    };
  });
}

// SVG Court Dimensions (10px per foot, half court)
export const COURT = {
  width: 500,
  height: 470,
  // Basket position (center of hoop)
  basketX: 250,
  basketY: 52,
  // Court boundaries
  baseline: 0,
  halfCourt: 470,
  sidelines: { left: 0, right: 500 },
  // Key dimensions
  keyWidth: 160, // 16 feet
  keyHeight: 190, // 19 feet
  restrictedRadius: 40, // 4 feet
  // Three-point line
  cornerThreeY: 140, // Where corner 3 ends
  threePointRadius: 238, // 23.75 feet (arc portion)
  cornerThreeX: 30, // Distance from sideline to corner 3 line
};

// Zone SVG paths/geometries
export const ZONE_PATHS = {
  // Restricted Area - circle around basket
  'Restricted Area': {
    type: 'circle' as const,
    cx: COURT.basketX,
    cy: COURT.basketY,
    r: COURT.restrictedRadius,
  },

  // Paint (Non-RA) - rectangle minus restricted circle
  'In The Paint (Non-RA)': {
    type: 'path' as const,
    // Paint rectangle from baseline, centered, minus the restricted area
    d: `M ${COURT.basketX - COURT.keyWidth / 2} 0
        L ${COURT.basketX - COURT.keyWidth / 2} ${COURT.keyHeight}
        L ${COURT.basketX + COURT.keyWidth / 2} ${COURT.keyHeight}
        L ${COURT.basketX + COURT.keyWidth / 2} 0
        Z`,
  },

  // Left Corner 3
  'Left Corner 3': {
    type: 'path' as const,
    d: `M 0 0
        L ${COURT.cornerThreeX} 0
        L ${COURT.cornerThreeX} ${COURT.cornerThreeY}
        L 0 ${COURT.cornerThreeY}
        Z`,
  },

  // Right Corner 3
  'Right Corner 3': {
    type: 'path' as const,
    d: `M ${COURT.width - COURT.cornerThreeX} 0
        L ${COURT.width} 0
        L ${COURT.width} ${COURT.cornerThreeY}
        L ${COURT.width - COURT.cornerThreeX} ${COURT.cornerThreeY}
        Z`,
  },

  // Above the Break 3 - arc from corners to half court
  'Above the Break 3': {
    type: 'path' as const,
    // Arc from left corner up and around to right corner, then to half court edges
    d: `M ${COURT.cornerThreeX} ${COURT.cornerThreeY}
        L ${COURT.cornerThreeX} ${COURT.cornerThreeY}
        A ${COURT.threePointRadius} ${COURT.threePointRadius} 0 0 1 ${COURT.width - COURT.cornerThreeX} ${COURT.cornerThreeY}
        L ${COURT.width - COURT.cornerThreeX} ${COURT.halfCourt}
        L ${COURT.cornerThreeX} ${COURT.halfCourt}
        Z`,
  },

  // Mid-Range - inside 3pt arc, outside paint
  'Mid-Range': {
    type: 'path' as const,
    // Complex path: 3pt arc interior minus paint rectangle
    d: `M ${COURT.cornerThreeX} 0
        L ${COURT.cornerThreeX} ${COURT.cornerThreeY}
        A ${COURT.threePointRadius} ${COURT.threePointRadius} 0 0 1 ${COURT.width - COURT.cornerThreeX} ${COURT.cornerThreeY}
        L ${COURT.width - COURT.cornerThreeX} 0
        L ${COURT.basketX + COURT.keyWidth / 2} 0
        L ${COURT.basketX + COURT.keyWidth / 2} ${COURT.keyHeight}
        L ${COURT.basketX - COURT.keyWidth / 2} ${COURT.keyHeight}
        L ${COURT.basketX - COURT.keyWidth / 2} 0
        Z`,
  },
};

// Display names for zones (shorter versions for tooltips)
export const ZONE_DISPLAY_NAMES: Record<ZoneName, string> = {
  'Restricted Area': 'Restricted Area',
  'In The Paint (Non-RA)': 'Paint (Non-RA)',
  'Mid-Range': 'Mid-Range',
  'Left Corner 3': 'Left Corner 3',
  'Right Corner 3': 'Right Corner 3',
  'Above the Break 3': 'Above the Break 3',
};
