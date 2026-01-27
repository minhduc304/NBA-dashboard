"""
The Odds API Client

Low-level API client for the-odds-api.com
"""

import logging
import os
import requests
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when API quota is exhausted or rate limited."""

    def __init__(self, message: str, quota_remaining: int = 0):
        super().__init__(message)
        self.quota_remaining = quota_remaining


class OddsAPI:
    """Client for The Odds API."""

    BASE_URL = "https://api.the-odds-api.com/v4"

    # Player prop markets we care about
    PLAYER_PROP_MARKETS = [
        'player_points',
        'player_rebounds',
        'player_assists',
        'player_threes',
        'player_blocks',
        'player_steals',
        'player_turnovers',
        'player_blocks_steals',
        'player_points_rebounds_assists',
        'player_points_rebounds',
        'player_points_assists',
        'player_rebounds_assists',
    ]

    # Request timeout in seconds (connect, read)
    DEFAULT_TIMEOUT = (10, 30)

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize API client.

        Args:
            api_key: API key or comma-separated list of keys (defaults to ODDS_API_KEY env var)
                     Multiple keys will be rotated automatically when quota is exhausted.
        """
        keys_str = api_key or os.getenv('ODDS_API_KEY')
        if not keys_str:
            raise ValueError("ODDS_API_KEY not found in environment")

        # Support multiple comma-separated keys
        self._api_keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        self._current_key_index = 0
        self.api_key = self._api_keys[0]

        self.session = requests.Session()
        self._requests_remaining = None
        self._requests_used = None

    def _rotate_key(self) -> bool:
        """
        Rotate to the next API key.

        Returns:
            True if successfully rotated, False if no more keys available.
        """
        if self._current_key_index < len(self._api_keys) - 1:
            self._current_key_index += 1
            self.api_key = self._api_keys[self._current_key_index]
            logger.info(
                "Rotated to API key %d of %d",
                self._current_key_index + 1,
                len(self._api_keys)
            )
            return True
        return False

    @property
    def keys_remaining(self) -> int:
        """Return number of unused API keys."""
        return len(self._api_keys) - self._current_key_index - 1

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request and track quota. Auto-rotates keys on quota exhaustion."""
        url = f"{self.BASE_URL}/{endpoint}"

        while True:
            request_params = {'apiKey': self.api_key}
            if params:
                request_params.update(params)

            response = self.session.get(url, params=request_params, timeout=self.DEFAULT_TIMEOUT)

            # Track API quota from headers
            self._requests_remaining = response.headers.get('x-requests-remaining')
            self._requests_used = response.headers.get('x-requests-used')

            # Check for rate limiting or quota exhaustion
            quota_exhausted = False
            if response.status_code == 429:
                quota_exhausted = True
            elif self._requests_remaining and int(self._requests_remaining) <= 0:
                quota_exhausted = True

            if quota_exhausted:
                # Try to rotate to next key
                if self._rotate_key():
                    logger.warning(
                        "API key exhausted, rotating to next key (%d/%d)",
                        self._current_key_index + 1,
                        len(self._api_keys)
                    )
                    continue  # Retry with new key
                else:
                    # No more keys available
                    remaining = int(self._requests_remaining) if self._requests_remaining else 0
                    raise RateLimitError(
                        f"All API keys exhausted. Keys used: {len(self._api_keys)}",
                        quota_remaining=remaining
                    )

            response.raise_for_status()
            return response.json()

    @property
    def quota_remaining(self) -> Optional[int]:
        """Return remaining API requests this month."""
        return int(self._requests_remaining) if self._requests_remaining else None

    def get_sports(self) -> List[Dict]:
        """Get list of available sports."""
        return self._request('sports')

    def get_nba_events(self) -> List[Dict]:
        """Get upcoming NBA events/games."""
        return self._request('sports/basketball_nba/events')

    def get_event_odds(
        self,
        event_id: str,
        markets: List[str],
        regions: str = 'us',
        odds_format: str = 'american',
    ) -> Dict:
        """
        Get odds for a specific event.

        Args:
            event_id: Event ID from get_nba_events
            markets: List of markets (e.g., ['player_points', 'player_rebounds'])
            regions: Region for sportsbooks (us, uk, eu, au)
            odds_format: american or decimal

        Returns:
            Event data with odds
        """
        params = {
            'regions': regions,
            'markets': ','.join(markets),
            'oddsFormat': odds_format,
        }
        return self._request(f'sports/basketball_nba/events/{event_id}/odds', params)

    def get_all_player_props(
        self,
        event_id: str,
        regions: str = 'us',
    ) -> Dict:
        """
        Get all player props for an event.

        Args:
            event_id: Event ID
            regions: Region for sportsbooks

        Returns:
            Event data with all player prop odds
        """
        return self.get_event_odds(
            event_id,
            markets=self.PLAYER_PROP_MARKETS,
            regions=regions,
        )

    def get_nba_player_props(
        self,
        markets: Optional[List[str]] = None,
        regions: str = 'us',
    ) -> List[Dict]:
        """
        Get player props for all upcoming NBA games.

        Args:
            markets: List of prop markets (defaults to all)
            regions: Region for sportsbooks

        Returns:
            List of events with player prop odds
        """
        if markets is None:
            markets = self.PLAYER_PROP_MARKETS

        events = self.get_nba_events()
        results = []

        for event in events:
            try:
                event_odds = self.get_event_odds(
                    event['id'],
                    markets=markets,
                    regions=regions,
                )
                results.append(event_odds)
            except requests.HTTPError as e:
                logger.error("Error fetching odds for %s: %s", event['id'], e)
                continue

        return results
