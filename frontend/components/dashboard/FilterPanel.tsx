'use client';

import { X, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

export interface GameLogFilters {
  season: 'all' | '2024-25' | '2025-26';
  location: 'all' | 'home' | 'away';
  result: 'all' | 'win' | 'loss';
  opponentAbbr: string | null;
}

export const DEFAULT_FILTERS: GameLogFilters = {
  season: 'all',
  location: 'all',
  result: 'all',
  opponentAbbr: null,
};

interface FilterPanelProps {
  isOpen: boolean;
  filters: GameLogFilters;
  onFiltersChange: (filters: GameLogFilters) => void;
  onClose: () => void;
  availableOpponents: string[];
  availableSeasons: string[];
}

// Toggle button group component
function ToggleGroup<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="flex gap-1 p-1 rounded-lg bg-secondary/50">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            'flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200',
            value === option.value
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function FilterPanel({
  isOpen,
  filters,
  onFiltersChange,
  onClose,
  availableOpponents,
  availableSeasons,
}: FilterPanelProps) {
  if (!isOpen) return null;

  const updateFilter = <K extends keyof GameLogFilters>(
    key: K,
    value: GameLogFilters[K]
  ) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  const resetFilters = () => {
    onFiltersChange(DEFAULT_FILTERS);
  };

  const hasActiveFilters =
    filters.season !== 'all' ||
    filters.location !== 'all' ||
    filters.result !== 'all' ||
    filters.opponentAbbr !== null;

  // Build season options from available seasons
  const seasonOptions: { value: GameLogFilters['season']; label: string }[] = [
    { value: 'all', label: 'All' },
  ];
  if (availableSeasons.includes('2024-25')) {
    seasonOptions.push({ value: '2024-25', label: "24-25" });
  }
  if (availableSeasons.includes('2025-26')) {
    seasonOptions.push({ value: '2025-26', label: "25-26" });
  }

  return (
    <div className="w-[280px] bg-card border-l border-border flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h3 className="text-sm font-semibold">Filters</h3>
        <div className="flex items-center gap-1">
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={resetFilters}
              title="Reset filters"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Filter Sections */}
      <div className="p-4 space-y-5 flex-1 overflow-y-auto">
        {/* Season Filter */}
        {seasonOptions.length > 1 && (
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Season
            </label>
            <ToggleGroup
              value={filters.season}
              onChange={(value) => updateFilter('season', value)}
              options={seasonOptions}
            />
          </div>
        )}

        {/* Location Filter */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Location
          </label>
          <ToggleGroup
            value={filters.location}
            onChange={(value) => updateFilter('location', value)}
            options={[
              { value: 'all', label: 'All' },
              { value: 'home', label: 'Home' },
              { value: 'away', label: 'Away' },
            ]}
          />
        </div>

        {/* Result Filter */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Result
          </label>
          <ToggleGroup
            value={filters.result}
            onChange={(value) => updateFilter('result', value)}
            options={[
              { value: 'all', label: 'All' },
              { value: 'win', label: 'Wins' },
              { value: 'loss', label: 'Losses' },
            ]}
          />
        </div>

        {/* Opponent Filter */}
        {availableOpponents.length > 0 && (
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Opponent (H2H)
            </label>
            <Select
              value={filters.opponentAbbr || 'all'}
              onValueChange={(value) =>
                updateFilter('opponentAbbr', value === 'all' ? null : value)
              }
            >
              <SelectTrigger className="h-9 bg-secondary/50 border-0">
                <SelectValue placeholder="All opponents" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All opponents</SelectItem>
                {availableOpponents.sort().map((opp) => (
                  <SelectItem key={opp} value={opp}>
                    {opp}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {/* Footer with active filter count */}
      {hasActiveFilters && (
        <div className="p-4 border-t border-border">
          <p className="text-xs text-muted-foreground text-center">
            {[
              filters.season !== 'all' && `Season: ${filters.season}`,
              filters.location !== 'all' && `${filters.location === 'home' ? 'Home' : 'Away'} games`,
              filters.result !== 'all' && `${filters.result === 'win' ? 'Wins' : 'Losses'} only`,
              filters.opponentAbbr && `vs ${filters.opponentAbbr}`,
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
      )}
    </div>
  );
}

export default FilterPanel;
