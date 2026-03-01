'use client';

import { useState, useEffect, useCallback } from 'react';
import { TopNav } from '@/components/dashboard/TopNav';
import { fetchTopPicks, type ApiTopPick } from '@/lib/api';
import { TopPicksSection } from '@/components/screener/TopPicksSection';

export default function ScreenerPage() {
  const [topPicks, setTopPicks] = useState<ApiTopPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTopPicks();
      setTopPicks(data.picks);
      setLastUpdated(data.lastUpdated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="min-h-screen bg-background">
      <TopNav />

      <main className="pt-[var(--topnav-height)] px-4 sm:px-6 lg:px-8 pb-8 max-w-[1600px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mt-6 mb-5">
          <div>
            <h2 className="text-xl font-display font-bold tracking-tight">Underdog vs Sharp Books</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Top 20 edges — Underdog even-odds lines vs devigged DraftKings, FanDuel, BetMGM
            </p>
          </div>
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              <span className="font-mono">{lastUpdated}</span>
            </span>
          )}
        </div>

        {/* Content */}
        {error ? (
          <div className="flex items-center justify-center h-64 text-destructive text-sm">
            {error}
          </div>
        ) : (
          <TopPicksSection picks={topPicks} loading={loading} />
        )}
      </main>
    </div>
  );
}
