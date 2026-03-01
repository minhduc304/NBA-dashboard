/**
 * Assist Zones Utilities
 * Types, color coding, and formatting for assist zones visualization
 */

// Zone names for assist zones (same as shooting zones)
export const ASSIST_ZONE_NAMES = [
  'Restricted Area',
  'In The Paint (Non-RA)',
  'Mid-Range',
  'Left Corner 3',
  'Right Corner 3',
  'Above the Break 3',
] as const;

export type AssistZoneName = typeof ASSIST_ZONE_NAMES[number];

// OKLCH color values for defensive ranking
const COLORS = {
  green: { l: 0.65, c: 0.20, h: 145 },   // Weak defense (21-30) - favorable
  yellow: { l: 0.80, c: 0.18, h: 85 },   // Average defense (11-20) - neutral
  red: { l: 0.60, c: 0.22, h: 25 },      // Strong defense (1-10) - unfavorable
  primary: { l: 0.50, c: 0.20, h: 265 }, // Primary color for heat map
  neutral: { l: 0.25, c: 0.01, h: 285 }, // No data
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
 * Get border color based on opponent defensive ranking
 * Green = weak defense (21-30), Yellow = average (11-20), Red = strong (1-10)
 */
export function getDefensiveRankColor(rank: number, hasData: boolean = true): string {
  if (!hasData || rank === 0) {
    return interpolateOklch(COLORS.neutral, COLORS.neutral, 1);
  }

  if (rank >= 21) {
    // Weak defense - favorable matchup
    return interpolateOklch(COLORS.green, COLORS.green, 1);
  } else if (rank >= 11) {
    // Average defense - neutral matchup
    return interpolateOklch(COLORS.yellow, COLORS.yellow, 1);
  } else {
    // Strong defense - unfavorable matchup
    return interpolateOklch(COLORS.red, COLORS.red, 1);
  }
}

/**
 * Get fill color for assist heat map based on percentage of total assists
 * Higher percentage = darker/more saturated color
 */
export function getAssistHeatColor(percentage: number, hasData: boolean = true): string {
  if (!hasData) {
    return interpolateOklch(COLORS.neutral, COLORS.neutral, 1);
  }

  // Normalize to 0-1 range (0% to 50%+ for assists)
  // Most zones will be 5-30%, so we scale accordingly
  const normalized = Math.min(1, percentage / 40);

  // Interpolate from very faint primary to full primary
  const faintPrimary = { ...COLORS.primary, l: 0.85, c: 0.05 };
  return interpolateOklch(faintPrimary, COLORS.primary, normalized);
}

/**
 * Get CSS class for defensive rank text color
 */
export function getDefensiveRankTextClass(rank: number): string {
  if (rank === 0) return 'text-muted-foreground';
  if (rank >= 21) return 'text-success';
  if (rank >= 11) return 'text-accent';
  return 'text-destructive';
}

/**
 * Get descriptive text for defensive rank
 */
export function getDefensiveRankLabel(rank: number): string {
  if (rank === 0) return 'No Data';
  if (rank >= 21) return 'Weak Defense';
  if (rank >= 11) return 'Average Defense';
  return 'Strong Defense';
}

/**
 * Format assist percentage
 */
export function formatAssistPct(pct: number): string {
  return `${pct.toFixed(1)}%`;
}

/**
 * Format assist count with total
 */
export function formatAssistCount(count: number, total: number): string {
  if (total === 0) return `${count} (0%)`;
  const pct = (count / total) * 100;
  return `${count} of ${total} (${pct.toFixed(1)}%)`;
}

/**
 * Format defensive FG%
 */
export function formatDefFgPct(pct: number): string {
  return `${(pct * 100).toFixed(1)}%`;
}

/**
 * Sort zones by assist count (descending)
 */
export function sortZonesByAssists<T extends { playerAssists: number }>(zones: T[]): T[] {
  return [...zones].sort((a, b) => b.playerAssists - a.playerAssists);
}

// Display names for zones (same as shooting zones)
export const ZONE_DISPLAY_NAMES: Record<AssistZoneName, string> = {
  'Restricted Area': 'Restricted Area',
  'In The Paint (Non-RA)': 'Paint (Non-RA)',
  'Mid-Range': 'Mid-Range',
  'Left Corner 3': 'Left Corner 3',
  'Right Corner 3': 'Right Corner 3',
  'Above the Break 3': 'Above the Break 3',
};
