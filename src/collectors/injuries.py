"""Injuries Collector - Collects current injury reports."""

import logging
from typing import Dict, List, Optional
import sqlite3
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


class InjuriesCollector:
    """Collects current injury report from NBA.com with ESPN as fallback."""

    def __init__(self, db_path: str):
        """
        Initialize collector.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def collect(self) -> Dict[str, any]:
        """
        Collect current injury report.

        Tries NBA.com first, falls back to ESPN if unavailable.
        Appends to player_injuries table with collection_date to preserve history.

        Returns:
            Dictionary with collection stats: inserted, source, errors
        """
        stats = {'inserted': 0, 'source': None, 'errors': []}
        injuries = []

        logger.info("Collecting injury report...")

        # Try NBA.com first
        try:
            injuries = self._fetch_from_nba_com()
            stats['source'] = 'nba.com'
            logger.info("Found %d injuries from NBA.com", len(injuries))
        except Exception as e:
            stats['errors'].append(f"NBA.com: {e}")
            logger.warning("NBA.com failed: %s", e)

            # Fallback to ESPN
            try:
                injuries = self._fetch_from_espn()
                stats['source'] = 'espn'
                logger.info("Found %d injuries from ESPN", len(injuries))
            except Exception as e2:
                stats['errors'].append(f"ESPN: {e2}")
                logger.error("ESPN also failed: %s", e2)
                return stats

        if not injuries:
            logger.warning("No injuries found from any source")
            return stats

        # Insert injuries into database
        stats['inserted'] = self._save_injuries(injuries, stats['source'])

        logger.info("Injury collection complete! Source: %s, Inserted/Updated: %d",
                   stats['source'], stats['inserted'])

        return stats

    def _fetch_from_nba_com(self) -> List[Dict]:
        """Fetch injury data from NBA.com."""
        url = "https://cdn.nba.com/static/json/liveData/injuries/injuries_all.json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.nba.com/',
            'Accept': 'application/json'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        injuries = []
        for team in data.get('teams', []):
            team_id = team.get('teamId')
            for player in team.get('players', []):
                injuries.append({
                    'player_id': player.get('personId'),
                    'player_name': f"{player.get('firstName', '')} {player.get('lastName', '')}".strip(),
                    'team_id': team_id,
                    'status': player.get('injuryStatus', 'Unknown'),
                    'description': player.get('reason', '')
                })

        return injuries

    def _fetch_from_espn(self) -> List[Dict]:
        """Fetch injury data from ESPN API as fallback."""
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        injuries = []
        for team in data.get('injuries', []):
            for injury in team.get('injuries', []):
                athlete_data = injury.get('athlete', {})

                # Extract player ID from links if available
                player_id = None
                for link in athlete_data.get('links', []):
                    href = link.get('href', '')
                    if '/id/' in href:
                        try:
                            player_id = int(href.split('/id/')[1].split('/')[0])
                        except (ValueError, IndexError):
                            pass
                        break

                injuries.append({
                    'player_id': player_id,
                    'player_name': athlete_data.get('displayName', ''),
                    'team_id': None,  # ESPN doesn't provide team_id directly
                    'status': injury.get('status', 'Unknown'),
                    'description': injury.get('longComment', injury.get('shortComment', ''))
                })

        return injuries

    def _save_injuries(self, injuries: List[Dict], source: str) -> int:
        """Save injuries to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        collection_date = datetime.now().strftime('%Y-%m-%d')
        inserted = 0

        for injury in injuries:
            try:
                cursor.execute('''
                    INSERT INTO player_injuries
                    (player_id, player_name, team_id, injury_status, injury_description, collection_date, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(player_id, collection_date) DO UPDATE SET
                        injury_status = excluded.injury_status,
                        injury_description = excluded.injury_description,
                        source = excluded.source
                ''', (
                    injury.get('player_id'),
                    injury.get('player_name'),
                    injury.get('team_id'),
                    injury.get('status'),
                    injury.get('description'),
                    collection_date,
                    source
                ))

                if cursor.rowcount > 0:
                    inserted += 1

            except sqlite3.Error as e:
                logger.debug("Error saving injury for player %s: %s", injury.get('player_name'), e)
                continue

        conn.commit()
        conn.close()

        return inserted

    def get_current_injuries(self) -> List[Dict]:
        """Get the most recent injury report from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM player_injuries
            WHERE collection_date = (
                SELECT MAX(collection_date) FROM player_injuries
            )
        ''')

        injuries = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return injuries

    def get_injury_for_player(self, player_id: int) -> Optional[Dict]:
        """Get current injury status for a specific player."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM player_injuries
            WHERE player_id = ?
            ORDER BY collection_date DESC
            LIMIT 1
        ''', (player_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None
