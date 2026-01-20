'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchPlayerGameLogs,
  fetchPlayerById,
  fetchPlayerProps,
  fetchPlayTypeMatchup,
  type ApiGameLog,
  type ApiPlayer,
  type ApiPropLine,
  type ApiPlayTypeMatchup,
} from '@/lib/api';
import { STAT_TO_API_FIELD, type StatCategory } from '@/lib/data';

// Hook for fetching player season stats
export function usePlayerStats(playerId: number | null) {
  const [playerStats, setPlayerStats] = useState<ApiPlayer | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!playerId || isNaN(playerId)) {
      setPlayerStats(null);
      return;
    }

    const loadPlayerStats = async () => {
      setIsLoading(true);
      try {
        const stats = await fetchPlayerById(playerId);
        setPlayerStats(stats);
      } catch (err) {
        console.error('Failed to fetch player stats:', err);
        setPlayerStats(null);
      } finally {
        setIsLoading(false);
      }
    };

    loadPlayerStats();
  }, [playerId]);

  return { playerStats, isLoading };
}

// Hook for fetching player props
export function usePlayerProps(playerId: number | null) {
  const [props, setProps] = useState<ApiPropLine[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!playerId || isNaN(playerId)) {
      setProps([]);
      return;
    }

    const loadPlayerProps = async () => {
      setIsLoading(true);
      try {
        const response = await fetchPlayerProps(playerId);
        setProps(response.props);
      } catch (err) {
        console.error('Failed to fetch player props:', err);
        setProps([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadPlayerProps();
  }, [playerId]);

  return { props, isLoading };
}

// Hook for fetching player game logs
export function usePlayerGameLogs(
  playerId: number | null,
  gamesCount: number,
  activeStat: StatCategory
) {
  const [gameLogs, setGameLogs] = useState<ApiGameLog[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const handleRetry = useCallback(() => {
    setRetryCount(prev => prev + 1);
  }, []);

  useEffect(() => {
    if (!playerId || isNaN(playerId)) {
      setGameLogs([]);
      return;
    }

    const loadGameLogs = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const statColumn = STAT_TO_API_FIELD[activeStat];
        const statCategoryParam = typeof statColumn === 'string' ? statColumn : statColumn[0];

        const logs = await fetchPlayerGameLogs(playerId, gamesCount, statCategoryParam);
        setGameLogs(logs);
      } catch (err) {
        console.error('Failed to fetch game logs:', err);
        setError(err instanceof Error ? err.message : 'Failed to load game data');
        setGameLogs([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadGameLogs();
  }, [playerId, gamesCount, activeStat, retryCount]);

  return { gameLogs, isLoading, error, handleRetry };
}

// Hook for fetching play type matchups
export function usePlayTypeMatchups(playerId: number | null, opponentId: number | null) {
  const [matchups, setMatchups] = useState<ApiPlayTypeMatchup[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const handleRetry = useCallback(() => {
    setRetryCount(prev => prev + 1);
  }, []);

  useEffect(() => {
    if (!playerId || isNaN(playerId) || !opponentId) {
      setMatchups([]);
      setError(null);
      return;
    }

    const loadMatchups = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetchPlayTypeMatchup(playerId, opponentId);
        setMatchups(response.matchups);
      } catch (err) {
        console.error('Failed to fetch play type matchup:', err);
        setError('Unable to load play type data');
        setMatchups([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadMatchups();
  }, [playerId, opponentId, retryCount]);

  return { matchups, isLoading, error, handleRetry };
}
