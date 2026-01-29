'use client';

import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ReferenceLine,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { NBA_TEAMS, type ChartDataPoint, type StatCategory } from '@/lib/data';
import { TeamLogo } from '@/components/ui/team-logo';
import { type ApiUpcomingMatchupContext } from '@/lib/api';

// NBA Team ID mapping for SVG logos
const TEAM_IDS: Record<string, number> = {
  ATL: 1610612737, BOS: 1610612738, BKN: 1610612751, CHA: 1610612766,
  CHI: 1610612741, CLE: 1610612739, DAL: 1610612742, DEN: 1610612743,
  DET: 1610612765, GSW: 1610612744, HOU: 1610612745, IND: 1610612754,
  LAC: 1610612746, LAL: 1610612747, MEM: 1610612763, MIA: 1610612748,
  MIL: 1610612749, MIN: 1610612750, NOP: 1610612740, NYK: 1610612752,
  OKC: 1610612760, ORL: 1610612753, PHI: 1610612755, PHX: 1610612756,
  POR: 1610612757, SAC: 1610612758, SAS: 1610612759, TOR: 1610612761,
  UTA: 1610612762, WAS: 1610612764,
};

// Helper to format rank display with color
function RankBadge({ rank, label }: { rank: number | null | undefined; label: string }) {
  if (rank == null) return null;

  // Color based on rank: 1-10 = green (good matchup), 11-20 = yellow, 21-30 = red (bad matchup)
  const colorClass = rank <= 10
    ? 'text-green-400'
    : rank <= 20
    ? 'text-amber-400'
    : 'text-red-400';

  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-mono font-semibold ${colorClass}`}>#{rank}</span>
    </div>
  );
}

// Helper to format stat display
function StatDisplay({ value, label, decimals = 1 }: { value: number | null | undefined; label: string; decimals?: number }) {
  if (value == null) return null;

  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-semibold">{value.toFixed(decimals)}</span>
    </div>
  );
}

// Stat-specific tooltip content for upcoming games
interface FutureGameTooltipProps {
  data: ChartDataPoint;
  statCategory: StatCategory;
}

function FutureGameTooltipContent({ data, statCategory }: FutureGameTooltipProps) {
  const ctx = data.upcomingContext;

  // Points-related stats
  if (statCategory === 'Points' || statCategory === 'Pts+Ast' || statCategory === 'Pts+Reb' || statCategory === 'PRA') {
    return (
      <div className="space-y-1 border-t border-border pt-2 mt-2">
        <div className="text-xs font-semibold text-muted-foreground mb-1">Defensive Context</div>
        {ctx?.dszName && <RankBadge rank={ctx.dszRank} label={`D-rank vs ${ctx.dszName}`} />}
        {ctx?.dptName && <RankBadge rank={ctx.dptRank} label={`D-rank vs ${ctx.dptName}`} />}
        {ctx?.dsz2Name && <RankBadge rank={ctx.dsz2Rank} label={`D-rank vs ${ctx.dsz2Name}`} />}
        <StatDisplay value={ctx?.defRtg} label="DefRtg" />
        <StatDisplay value={ctx?.pace} label="Pace" />
        {ctx?.dpt2Name && <RankBadge rank={ctx.dpt2Rank} label={`D-rank vs ${ctx.dpt2Name}`} />}
      </div>
    );
  }

  // Assist-related stats
  if (statCategory === 'Assists' || statCategory === 'Ast+Reb') {
    return (
      <div className="space-y-1 border-t border-border pt-2 mt-2">
        <div className="text-xs font-semibold text-muted-foreground mb-1">Defensive Context</div>
        {ctx?.dazName && <RankBadge rank={ctx.dazRank} label={`D-rank vs ${ctx.dazName}`} />}
        {ctx?.daz2Name && <RankBadge rank={ctx.daz2Rank} label={`D-rank vs ${ctx.daz2Name}`} />}
        <StatDisplay value={ctx?.assistsAllowed} label="Assists Allowed" />
        <StatDisplay value={ctx?.defRtg} label="DefRtg" />
      </div>
    );
  }

  // Rebound-related stats (ranks are stored in dsz/dpt fields)
  if (statCategory === 'Rebounds') {
    return (
      <div className="space-y-1 border-t border-border pt-2 mt-2">
        <div className="text-xs font-semibold text-muted-foreground mb-1">Defensive Context</div>
        <RankBadge rank={ctx?.dszRank} label="D-rank vs Total Reb" />
        <RankBadge rank={ctx?.dsz2Rank} label="D-rank vs OREB" />
        <RankBadge rank={ctx?.dptRank} label="D-rank vs DREB" />
        <StatDisplay value={ctx?.pace} label="Pace" />
      </div>
    );
  }

  // Default: just show pace and def rating if available
  return ctx ? (
    <div className="space-y-1 border-t border-border pt-2 mt-2">
      <div className="text-xs font-semibold text-muted-foreground mb-1">Defensive Context</div>
      <StatDisplay value={ctx.defRtg} label="DefRtg" />
      <StatDisplay value={ctx.pace} label="Pace" />
    </div>
  ) : null;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: ChartDataPoint & { isOver: boolean } }>;
  lineValue: number;
  statCategory: StatCategory;
}

function CustomTooltip({ active, payload, lineValue, statCategory }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;
  if (data.isFuture) {
    return (
      <div className="bg-popover border border-border rounded-lg p-3 shadow-xl min-w-[200px]">
        <div className="text-sm font-medium">Upcoming Game</div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{data.date} vs</span>
          <TeamLogo team={data.opponent} size={16} />
          <span>{NBA_TEAMS[data.opponent]?.name || data.opponent}</span>
        </div>
        {data.value !== null && (
          <div className="text-xs text-muted-foreground mt-1">
            Projected: <span className="font-mono font-semibold">{data.value.toFixed(1)}</span>
          </div>
        )}
        <FutureGameTooltipContent data={data} statCategory={statCategory} />
      </div>
    );
  }

  const isOver = data.value !== null && data.value > lineValue;

  // Format margin display (e.g., "W +12" or "L -5")
  const marginDisplay = data.wl && data.gameMargin !== null
    ? `${data.wl} ${data.gameMargin >= 0 ? '+' : ''}${data.gameMargin}`
    : null;

  return (
    <div className="bg-popover border border-border rounded-lg p-3 shadow-xl min-w-[180px]">
      {/* Header: Date vs Opponent | W/L Margin */}
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{data.date} vs</span>
          <TeamLogo team={data.opponent} size={18} />
        </div>
        {marginDisplay && (
          <span className={`text-xs font-semibold ${data.wl === 'W' ? 'text-green-500' : 'text-red-500'}`}>
            {marginDisplay}
          </span>
        )}
      </div>

      {/* Minutes */}
      {data.min !== null && (
        <div className="text-xs text-muted-foreground mb-2">
          {Math.floor(data.min)} min
        </div>
      )}

      {/* Stat Value with Over/Under */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl font-bold font-mono">{data.value}</span>
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded ${
            isOver ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'
          }`}
        >
          {isOver ? 'OVER' : 'UNDER'}
        </span>
      </div>

      {/* Scoring Breakdown */}
      {(data.fgm !== null || data.fg3m !== null || data.ftm !== null) && (
        <div className="flex gap-3 text-xs text-muted-foreground border-t border-border pt-2">
          {data.fgm !== null && data.fga !== null && (
            <span>FG: {data.fgm}/{data.fga}</span>
          )}
          {data.fg3m !== null && data.fg3a !== null && (
            <span>3P: {data.fg3m}/{data.fg3a}</span>
          )}
          {data.ftm !== null && data.fta !== null && (
            <span>FT: {data.ftm}/{data.fta}</span>
          )}
        </div>
      )}

      {/* Rebound Breakdown */}
      {(data.oreb !== null || data.dreb !== null) && (
        <div className="flex gap-3 text-xs text-muted-foreground border-t border-border pt-2 mt-2">
          {data.oreb !== null && (
            <span>OREB: {data.oreb}</span>
          )}
          {data.dreb !== null && (
            <span>DREB: {data.dreb}</span>
          )}
          {data.oreb !== null && data.dreb !== null && (
            <span className="text-muted-foreground/60">Total: {data.oreb + data.dreb}</span>
          )}
        </div>
      )}

      {/* DNP Players */}
      {data.dnpPlayers && data.dnpPlayers.length > 0 && (
        <div className="border-t border-border pt-2 mt-2">
          <div className="text-xs font-semibold text-muted-foreground mb-1">DNP (Teammates)</div>
          <div className="space-y-1">
            {data.dnpPlayers.map((dnp, idx) => (
              <div key={idx} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">
                  {dnp.playerName}
                </span>
                <span className="font-mono font-semibold text-amber-500">
                  {dnp.seasonAvg.toFixed(1)} avg
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface CustomXAxisTickProps {
  x?: number;
  y?: number;
  payload?: { value: string; index: number };
  chartData: ChartDataPoint[];
}

function CustomXAxisTick({ x, y, payload, chartData }: CustomXAxisTickProps) {
  if (!payload || x === undefined || y === undefined) return null;

  const dataPoint = chartData[payload.index];
  if (!dataPoint) return null;

  const teamId = TEAM_IDS[dataPoint.opponent];
  const logoUrl = teamId
    ? `https://cdn.nba.com/logos/nba/${teamId}/global/L/logo.svg`
    : null;

  // Parse date - format is "Nov 01"
  const [month, day] = dataPoint.date.split(' ');

  return (
    <g transform={`translate(${x},${y})`}>
      {/* Team logo - larger to match bar width */}
      {logoUrl ? (
        <image
          href={logoUrl}
          x={-16}
          y={2}
          width={32}
          height={32}
        />
      ) : (
        <>
          <circle cx={0} cy={18} r={16} fill={NBA_TEAMS[dataPoint.opponent]?.color || '#666'} />
          <text x={0} y={22} textAnchor="middle" fill="white" fontSize={10} fontWeight="bold">
            {dataPoint.opponent}
          </text>
        </>
      )}
      {/* Month */}
      <text
        x={0}
        y={46}
        textAnchor="middle"
        fill="oklch(0.55 0.02 250)"
        fontSize={9}
      >
        {month}
      </text>
      {/* Day */}
      <text
        x={0}
        y={58}
        textAnchor="middle"
        fill="oklch(0.65 0.02 250)"
        fontSize={11}
        fontWeight="500"
      >
        {day}
      </text>
    </g>
  );
}

export interface HitRateInfo {
  hitRate: number;
  hitCount: number;
  totalGames: number;
}

interface StatsChartProps {
  data: ChartDataPoint[];
  initialLineValue?: number;
  onLineChange?: (value: number, hitRateInfo: HitRateInfo) => void;
  statCategory?: StatCategory;
}

export function StatsChart({ data, initialLineValue = 30.5, onLineChange, statCategory = 'Points' }: StatsChartProps) {
  const [mounted, setMounted] = useState(false);
  const [lineValue, setLineValue] = useState(initialLineValue);
  const [isDragging, setIsDragging] = useState(false);
  const chartContainerRef = useRef<HTMLDivElement>(null);

  // Sync line value when initialLineValue changes (e.g., when stat category changes)
  useEffect(() => {
    setLineValue(initialLineValue);
  }, [initialLineValue]);

  // Calculate max value from data for Y-axis range
  const maxDataValue = useMemo(() => {
    const values = data.filter(d => d.value !== null).map(d => d.value as number);
    return values.length > 0 ? Math.max(...values) : 0;
  }, [data]);

  // Y-axis domain: 0 to (max + 1), rounded up to nearest 5
  const yAxisMax = useMemo(() => {
    const max = Math.ceil((maxDataValue + 1) / 5) * 5;
    return max > 0 ? max : 5; // Ensure minimum of 5
  }, [maxDataValue]);

  // Snap to betting format (X.5)
  const snapToBettingFormat = useCallback((value: number): number => {
    return Math.floor(value) + 0.5;
  }, []);

  // Calculate hit rate based on line value
  const calculateHitRate = useCallback((line: number): HitRateInfo => {
    const gamesWithValues = data.filter(d => d.value !== null && !d.isFuture);
    const hitCount = gamesWithValues.filter(d => (d.value as number) > line).length;
    const totalGames = gamesWithValues.length;
    const hitRate = totalGames > 0 ? Math.round((hitCount / totalGames) * 100) : 0;
    return { hitRate, hitCount, totalGames };
  }, [data]);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Clamp a value to valid line bounds
  const clampLineValue = useCallback((value: number, maxY: number): number => {
    const clamped = Math.max(0.5, Math.min(maxY - 0.5, value));
    return snapToBettingFormat(clamped);
  }, [snapToBettingFormat]);

  // Clamp line value when yAxisMax changes (e.g., switching stat categories)
  // This ensures the line stays visible within the chart
  useEffect(() => {
    const clampedValue = clampLineValue(lineValue, yAxisMax);
    if (clampedValue !== lineValue) {
      setLineValue(clampedValue);
      if (onLineChange) {
        const hitRateInfo = calculateHitRate(clampedValue);
        onLineChange(clampedValue, hitRateInfo);
      }
    }
  }, [yAxisMax, lineValue, clampLineValue, calculateHitRate, onLineChange]);

  // Notify parent of initial hit rate
  useEffect(() => {
    if (mounted && onLineChange) {
      const hitRateInfo = calculateHitRate(lineValue);
      onLineChange(lineValue, hitRateInfo);
    }
  }, [mounted]);

  // Update line value when initial value changes (e.g., different player selected)
  useEffect(() => {
    // Clamp initialLineValue to valid range before setting
    const clampedValue = clampLineValue(initialLineValue, yAxisMax);
    setLineValue(clampedValue);
    if (onLineChange) {
      const hitRateInfo = calculateHitRate(clampedValue);
      onLineChange(clampedValue, hitRateInfo);
    }
  }, [initialLineValue, yAxisMax, clampLineValue, calculateHitRate, onLineChange]);

  // Handle mouse/touch events for dragging the line
  const handleMouseDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !chartContainerRef.current) return;

    const rect = chartContainerRef.current.getBoundingClientRect();
    const chartTop = 10;      // margin.top (must match BarChart margin)
    const chartBottom = 70;   // margin.bottom (must match BarChart margin)
    const xAxisHeight = 70;   // XAxis height (takes space from chart area)
    // Y plotting area excludes XAxis
    const yPlottingHeight = rect.height - chartTop - chartBottom - xAxisHeight;

    // Calculate Y position relative to Y plotting area
    const mouseY = e.clientY - rect.top - chartTop;
    const percentage = 1 - (mouseY / yPlottingHeight);

    // Convert to value
    let newValue = percentage * yAxisMax;
    newValue = Math.max(0.5, Math.min(yAxisMax - 0.5, newValue));
    newValue = snapToBettingFormat(newValue);

    if (newValue !== lineValue) {
      setLineValue(newValue);
      if (onLineChange) {
        const hitRateInfo = calculateHitRate(newValue);
        onLineChange(newValue, hitRateInfo);
      }
    }
  }, [isDragging, lineValue, yAxisMax, snapToBettingFormat, calculateHitRate, onLineChange]);

  // Handle touch events
  const handleTouchMove = useCallback((e: React.TouchEvent<HTMLDivElement>) => {
    if (!isDragging || !chartContainerRef.current) return;

    const touch = e.touches[0];
    const rect = chartContainerRef.current.getBoundingClientRect();
    const chartTop = 10;      // margin.top (must match BarChart margin)
    const chartBottom = 70;   // margin.bottom (must match BarChart margin)
    const xAxisHeight = 70;   // XAxis height (takes space from chart area)
    // Y plotting area excludes XAxis
    const yPlottingHeight = rect.height - chartTop - chartBottom - xAxisHeight;

    const touchY = touch.clientY - rect.top - chartTop;
    const percentage = 1 - (touchY / yPlottingHeight);

    let newValue = percentage * yAxisMax;
    newValue = Math.max(0.5, Math.min(yAxisMax - 0.5, newValue));
    newValue = snapToBettingFormat(newValue);

    if (newValue !== lineValue) {
      setLineValue(newValue);
      if (onLineChange) {
        const hitRateInfo = calculateHitRate(newValue);
        onLineChange(newValue, hitRateInfo);
      }
    }
  }, [isDragging, lineValue, yAxisMax, snapToBettingFormat, calculateHitRate, onLineChange]);

  // Add global mouse up listener
  useEffect(() => {
    const handleGlobalMouseUp = () => setIsDragging(false);
    window.addEventListener('mouseup', handleGlobalMouseUp);
    window.addEventListener('touchend', handleGlobalMouseUp);
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
      window.removeEventListener('touchend', handleGlobalMouseUp);
    };
  }, []);

  const chartData = useMemo(() => {
    return data.map((d) => ({
      ...d,
      isOver: d.value !== null && d.value > lineValue,
      displayValue: d.value ?? 0,
    }));
  }, [data, lineValue]);

  // Calculate bar size based on game count
  // More games = smaller bars, fewer games = larger bars
  const barSize = useMemo(() => {
    const gameCount = data.length;
    const maxBarWidth = 32;
    const minBarWidth = 8;

    // Scale bar width inversely with game count
    // 10 games = 32px, 50 games = 8px
    const calculated = Math.floor(40 - (gameCount * 0.64));
    return Math.max(minBarWidth, Math.min(maxBarWidth, calculated));
  }, [data.length]);

  if (!mounted) {
    return (
      <div className="w-full h-[450px] flex items-center justify-center">
        <div className="text-muted-foreground">Loading chart...</div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="w-full h-[450px] flex items-center justify-center">
        <div className="text-muted-foreground">No game data available</div>
      </div>
    );
  }

  return (
    <div
      ref={chartContainerRef}
      className="w-full h-[450px] relative select-none"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleMouseUp}
      style={{ cursor: isDragging ? 'ns-resize' : 'default' }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          margin={{ top: 10, right: 20, bottom: 70, left: 50 }}
          barCategoryGap={2}
          barSize={barSize}
        >
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={<CustomXAxisTick chartData={chartData} />}
            interval={0}
            height={70}
          />
          <YAxis
            domain={[0, yAxisMax]}
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'oklch(0.65 0.02 250)', fontSize: 12 }}
            tickFormatter={(value) => value.toString()}
            allowDataOverflow={false}
          />
          <Tooltip content={<CustomTooltip lineValue={lineValue} statCategory={statCategory} />} cursor={false} />

          {/* Draggable Reference Line - clamped to valid range */}
          <ReferenceLine
            y={Math.max(0.5, Math.min(yAxisMax - 0.5, lineValue))}
            stroke="oklch(0.80 0.18 85)"
            strokeWidth={3}
            strokeDasharray="8 4"
            style={{ cursor: 'ns-resize' }}
          />

          <Bar dataKey="displayValue" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => {
              if (entry.isFuture) {
                return (
                  <Cell
                    key={`cell-${index}`}
                    fill="transparent"
                    stroke="oklch(0.65 0.02 250)"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                  />
                );
              }
              return (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.isOver ? 'oklch(0.75 0.20 145)' : 'oklch(0.60 0.22 25)'}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Draggable Line Handle - positioned over the Y-axis area */}
      {(() => {
        // Chart layout constants (must match BarChart margin and XAxis height)
        const chartTopMargin = 10;    // margin.top
        const chartBottomMargin = 70; // margin.bottom
        const xAxisHeight = 70;       // XAxis height prop - takes space from chart area
        const totalHeight = 450;      // matches h-[450px]

        // The Y plotting area is the chart area minus the XAxis height
        // Chart area = totalHeight - topMargin - bottomMargin = 370px
        // Y plotting area = chartArea - xAxisHeight = 370 - 70 = 300px
        const chartAreaHeight = totalHeight - chartTopMargin - chartBottomMargin;
        const yPlottingAreaHeight = chartAreaHeight - xAxisHeight;

        // Clamp lineValue to valid range for display
        const safeLineValue = Math.max(0.5, Math.min(yAxisMax - 0.5, lineValue));

        // Calculate position: percentage of Y plotting area from top
        const valuePercentage = (yAxisMax - safeLineValue) / yAxisMax;
        const topPosition = chartTopMargin + valuePercentage * yPlottingAreaHeight;

        return (
          <>
            <div
              className="absolute left-0 flex items-center gap-2 cursor-ns-resize z-10"
              style={{
                top: `${topPosition}px`,
                transform: 'translateY(-50%)',
              }}
              onMouseDown={handleMouseDown}
              onTouchStart={handleMouseDown}
            >
              <div className="px-3 py-1.5 rounded-lg bg-amber-400 text-amber-950 text-sm font-bold font-mono shadow-lg hover:bg-amber-300 transition-colors flex items-center gap-1.5">
                <span className="text-xs opacity-70">≡</span>
                {safeLineValue}
              </div>
            </div>

            {/* Invisible drag area over the entire line */}
            <div
              className="absolute left-12 right-5 h-6 cursor-ns-resize z-10"
              style={{
                top: `${topPosition}px`,
                transform: 'translateY(-50%)',
              }}
              onMouseDown={handleMouseDown}
              onTouchStart={handleMouseDown}
            />
          </>
        );
      })()}
    </div>
  );
}
