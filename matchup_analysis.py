#!/usr/bin/env python3
"""
NBA Matchup Analysis Script (Enhanced)

Analyzes today's NBA games to find exploitable matchups by comparing:
- Player shooting zones vs team defensive zones (with league averages & rankings)
- Player play types vs team defensive play types (with league averages & rankings)
- Player assist zones vs team defensive zones

Features:
- League-average baselines for context
- Team defensive rankings (1-30) for each zone/play type
- Minimum sample size filters to avoid small-sample noise
- Confidence intervals to show reliability of advantages

Usage:
    python matchup_analysis.py                    # Analyze today's games
    python matchup_analysis.py --date 11/15/2025  # Analyze specific date
    python matchup_analysis.py --min-advantage 0.1  # Filter by advantage threshold
"""

import sqlite3
import argparse
from datetime import date
from typing import Dict, List, Optional
from nba_api.stats.endpoints import scoreboardv2, commonteamroster
from nba_api.stats.static import teams as teams_static
import time
import math


class MatchupAnalyzer:
    """Analyzes NBA matchups to find player advantages vs team defenses."""

    # Minimum sample sizes for reliable data
    MIN_FGA_PER_GAME = 1.0        # Shooting zones
    MIN_POSS_PER_GAME = 1.0       # Play types
    MIN_ASSISTS_TOTAL = 5         # Assist zones

    def __init__(self, db_path: str = 'nba_stats.db'):
        """Initialize the matchup analyzer."""
        self.db_path = db_path
        self.season = '2025-26'

        # Cache for league averages and rankings (computed once)
        self._league_avg_shooting = None
        self._league_avg_play_types = None
        self._team_rankings_shooting = None
        self._team_rankings_play_types = None

    def get_todays_games(self, game_date: Optional[str] = None) -> List[Dict]:
        """
        Get today's NBA games.

        Args:
            game_date: Optional date in MM/DD/YYYY format (defaults to today)

        Returns:
            List of game dictionaries with team info
        """
        if game_date is None:
            game_date = date.today().strftime('%m/%d/%Y')

        # Get team name mapping
        all_teams = teams_static.get_teams()
        team_map = {t['id']: t for t in all_teams}

        # Get scoreboard
        scoreboard = scoreboardv2.ScoreboardV2(game_date=game_date)
        games_df = scoreboard.game_header.get_data_frame()

        games = []
        for _, game in games_df.iterrows():
            visitor_id = game['VISITOR_TEAM_ID']
            home_id = game['HOME_TEAM_ID']

            games.append({
                'game_id': game['GAME_ID'],
                'visitor': {
                    'id': visitor_id,
                    'name': team_map[visitor_id]['full_name'],
                    'abbr': team_map[visitor_id]['abbreviation']
                },
                'home': {
                    'id': home_id,
                    'name': team_map[home_id]['full_name'],
                    'abbr': team_map[home_id]['abbreviation']
                },
                'status': game['GAME_STATUS_TEXT']
            })

        return games

    def get_league_average_shooting(self) -> Dict[str, float]:
        """
        Calculate league-average FG% for each shooting zone.

        Returns:
            Dict mapping zone_name -> league average FG%
        """
        if self._league_avg_shooting is not None:
            return self._league_avg_shooting

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate weighted average across all players
        cursor.execute("""
            SELECT
                zone_name,
                SUM(fgm * (SELECT games_played FROM player_stats ps WHERE ps.player_id = psz.player_id)) as total_fgm,
                SUM(fga * (SELECT games_played FROM player_stats ps WHERE ps.player_id = psz.player_id)) as total_fga
            FROM player_shooting_zones psz
            WHERE season = ?
            GROUP BY zone_name
        """, (self.season,))

        league_avg = {}
        for row in cursor.fetchall():
            zone_name, total_fgm, total_fga = row
            if total_fga and total_fga > 0:
                league_avg[zone_name] = total_fgm / total_fga

        conn.close()
        self._league_avg_shooting = league_avg
        return league_avg

    def get_league_average_play_types(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate league-average PPP and FG% for each play type.

        Returns:
            Dict mapping play_type -> {'ppp': X, 'fg_pct': Y}
        """
        if self._league_avg_play_types is not None:
            return self._league_avg_play_types

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate weighted average across all players
        cursor.execute("""
            SELECT
                play_type,
                SUM(points) as total_points,
                SUM(possessions) as total_poss,
                SUM(possessions * fg_pct) as weighted_fg_sum,
                SUM(possessions) as total_poss_for_fg
            FROM player_play_types
            WHERE season = ? AND play_type != 'NO_DATA'
            GROUP BY play_type
        """, (self.season,))

        league_avg = {}
        for row in cursor.fetchall():
            play_type, total_pts, total_poss, weighted_fg, total_poss_fg = row
            if total_poss and total_poss > 0:
                league_avg[play_type] = {
                    'ppp': total_pts / total_poss if total_poss > 0 else 0,
                    'fg_pct': weighted_fg / total_poss_fg if total_poss_fg > 0 else 0
                }

        conn.close()
        self._league_avg_play_types = league_avg
        return league_avg

    def get_team_defensive_rankings_shooting(self) -> Dict[str, List[tuple]]:
        """
        Get team defensive rankings for each shooting zone (1 = best defense).

        Returns:
            Dict mapping zone_name -> [(team_id, rank, opp_fg_pct), ...]
        """
        if self._team_rankings_shooting is not None:
            return self._team_rankings_shooting

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all zones
        cursor.execute("SELECT DISTINCT zone_name FROM team_defensive_zones WHERE season = ?", (self.season,))
        zones = [row[0] for row in cursor.fetchall()]

        rankings = {}
        for zone in zones:
            cursor.execute("""
                SELECT team_id, opp_fg_pct
                FROM team_defensive_zones
                WHERE zone_name = ? AND season = ?
                ORDER BY opp_fg_pct ASC
            """, (zone, self.season))

            # Rank teams (1 = lowest opp_fg_pct = best defense)
            zone_rankings = []
            for rank, (team_id, opp_fg_pct) in enumerate(cursor.fetchall(), 1):
                zone_rankings.append((team_id, rank, opp_fg_pct))

            rankings[zone] = zone_rankings

        conn.close()
        self._team_rankings_shooting = rankings
        return rankings

    def get_team_defensive_rankings_play_types(self) -> Dict[str, List[tuple]]:
        """
        Get team defensive rankings for each play type (1 = best defense).

        Returns:
            Dict mapping play_type -> [(team_id, rank, ppp), ...]
        """
        if self._team_rankings_play_types is not None:
            return self._team_rankings_play_types

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all play types
        cursor.execute("SELECT DISTINCT play_type FROM team_defensive_play_types WHERE season = ?", (self.season,))
        play_types = [row[0] for row in cursor.fetchall()]

        rankings = {}
        for play_type in play_types:
            cursor.execute("""
                SELECT team_id, ppp
                FROM team_defensive_play_types
                WHERE play_type = ? AND season = ?
                ORDER BY ppp ASC
            """, (play_type, self.season))

            # Rank teams (1 = lowest PPP = best defense)
            type_rankings = []
            for rank, (team_id, ppp) in enumerate(cursor.fetchall(), 1):
                type_rankings.append((team_id, rank, ppp))

            rankings[play_type] = type_rankings

        conn.close()
        self._team_rankings_play_types = rankings
        return rankings

    def get_team_rank(self, team_id: int, zone_or_type: str, is_shooting: bool = True) -> Optional[int]:
        """
        Get a team's defensive rank for a specific zone or play type.

        Args:
            team_id: Team ID
            zone_or_type: Zone name or play type name
            is_shooting: True for shooting zones, False for play types

        Returns:
            Rank (1-30) or None if not found
        """
        rankings = self.get_team_defensive_rankings_shooting() if is_shooting else self.get_team_defensive_rankings_play_types()

        if zone_or_type not in rankings:
            return None

        for tid, rank, _ in rankings[zone_or_type]:
            if tid == team_id:
                return rank

        return None

    def calculate_confidence_interval(self, pct: float, n_attempts: float, confidence: float = 0.95) -> tuple:
        """
        Calculate Wilson score confidence interval for a percentage.

        Args:
            pct: Observed percentage (0.0 to 1.0)
            n_attempts: Number of attempts
            confidence: Confidence level (default 0.95 for 95%)

        Returns:
            (lower_bound, upper_bound) as percentages
        """
        if n_attempts < 1:
            return (0.0, 1.0)

        # Wilson score interval
        z = 1.96 if confidence == 0.95 else 1.645  # z-score for confidence level

        p = pct
        n = n_attempts

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2*n)) / denominator
        margin = z * math.sqrt((p * (1-p) / n + z**2 / (4*n**2))) / denominator

        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)

        return (lower, upper)

    def get_team_key_players(self, team_id: int, top_n: int = 3) -> List[Dict]:
        """
        Get key players for a team based on points per game.

        Args:
            team_id: NBA API team ID
            top_n: Number of top players to return

        Returns:
            List of player dictionaries with stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get top scorers from the team
        try:
            roster = commonteamroster.CommonTeamRoster(team_id=team_id, season=self.season)
            roster_df = roster.common_team_roster.get_data_frame()
            player_ids = roster_df['PLAYER_ID'].tolist()

            if not player_ids:
                conn.close()
                return []

            # Get player stats
            placeholders = ','.join('?' * len(player_ids))
            query = f"""
                SELECT player_id, player_name, points, assists, rebounds, games_played
                FROM player_stats
                WHERE player_id IN ({placeholders})
                  AND season = ?
                  AND games_played > 0
                ORDER BY points DESC
                LIMIT ?
            """

            cursor.execute(query, player_ids + [self.season, top_n])
            players = []

            for row in cursor.fetchall():
                players.append({
                    'id': row[0],
                    'name': row[1],
                    'ppg': row[2],
                    'apg': row[3],
                    'rpg': row[4],
                    'games_played': row[5]
                })

            conn.close()
            time.sleep(0.6)  # Rate limiting for roster API call
            return players

        except Exception as e:
            print(f"  Warning: Could not get roster for team {team_id}: {e}")
            conn.close()
            return []

    def analyze_shooting_zones(self, player_id: int, opponent_team_id: int) -> List[Dict]:
        """
        Compare player shooting zones vs opponent defensive zones.

        Args:
            player_id: NBA API player ID
            opponent_team_id: Opponent team ID

        Returns:
            List of zone matchup dictionaries with advantages
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get player shooting zones
        cursor.execute("""
            SELECT zone_name, fg_pct, fga, fgm
            FROM player_shooting_zones
            WHERE player_id = ? AND season = ?
        """, (player_id, self.season))

        player_zones = {row[0]: {'fg_pct': row[1], 'fga': row[2], 'fgm': row[3]} for row in cursor.fetchall()}

        # Get opponent defensive zones
        cursor.execute("""
            SELECT zone_name, opp_fg_pct, opp_fga
            FROM team_defensive_zones
            WHERE team_id = ? AND season = ?
        """, (opponent_team_id, self.season))

        opp_zones = {row[0]: {'opp_fg_pct': row[1], 'opp_fga': row[2]} for row in cursor.fetchall()}

        # Get games played for per-game calculation
        cursor.execute("SELECT games_played FROM player_stats WHERE player_id = ?", (player_id,))
        result = cursor.fetchone()
        games_played = result[0] if result else 1

        conn.close()

        # Get league averages and rankings
        league_avg = self.get_league_average_shooting()
        rankings = self.get_team_defensive_rankings_shooting()

        # Calculate advantages
        matchups = []
        for zone_name in player_zones:
            if zone_name in opp_zones:
                player_pct = player_zones[zone_name]['fg_pct']
                player_fga = player_zones[zone_name]['fga']
                player_fgm = player_zones[zone_name]['fgm']
                opp_pct = opp_zones[zone_name]['opp_fg_pct']
                league_pct = league_avg.get(zone_name, 0.40)  # Default 40% if not found

                # Apply minimum sample size filter
                if player_fga < self.MIN_FGA_PER_GAME:
                    continue

                # Calculate advantages
                advantage_vs_defense = player_pct - opp_pct
                player_vs_league = player_pct - league_pct
                defense_vs_league = opp_pct - league_pct

                # Get team rank
                team_rank = self.get_team_rank(opponent_team_id, zone_name, is_shooting=True)

                # Calculate confidence interval for player shooting
                total_attempts = player_fga * games_played
                ci_lower, ci_upper = self.calculate_confidence_interval(player_pct, total_attempts)

                matchups.append({
                    'zone': zone_name,
                    'player_fg_pct': player_pct,
                    'opp_fg_pct': opp_pct,
                    'league_avg': league_pct,
                    'advantage': advantage_vs_defense,
                    'player_vs_league': player_vs_league,
                    'defense_vs_league': defense_vs_league,
                    'player_fga': player_fga,
                    'team_rank': team_rank,
                    'total_attempts': total_attempts,
                    'ci_lower': ci_lower,
                    'ci_upper': ci_upper,
                    'significance': abs(advantage_vs_defense) * player_fga
                })

        # Sort by significance
        matchups.sort(key=lambda x: x['significance'], reverse=True)
        return matchups

    def analyze_play_types(self, player_id: int, opponent_team_id: int) -> List[Dict]:
        """
        Compare player offensive play types vs opponent defensive play types.

        Args:
            player_id: NBA API player ID
            opponent_team_id: Opponent team ID

        Returns:
            List of play type matchup dictionaries with advantages
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get player offensive play types
        cursor.execute("""
            SELECT play_type, ppp, fg_pct, points_per_game, poss_per_game
            FROM player_play_types
            WHERE player_id = ? AND season = ? AND play_type != 'NO_DATA'
        """, (player_id, self.season))

        player_types = {row[0]: {'ppp': row[1], 'fg_pct': row[2], 'ppg': row[3], 'poss_pg': row[4]}
                        for row in cursor.fetchall()}

        # Get opponent defensive play types
        cursor.execute("""
            SELECT play_type, ppp, fg_pct, points_per_game, poss_per_game
            FROM team_defensive_play_types
            WHERE team_id = ? AND season = ?
        """, (opponent_team_id, self.season))

        opp_types = {row[0]: {'ppp': row[1], 'fg_pct': row[2], 'ppg': row[3], 'poss_pg': row[4]}
                     for row in cursor.fetchall()}

        conn.close()

        # Get league averages and rankings
        league_avg = self.get_league_average_play_types()
        rankings = self.get_team_defensive_rankings_play_types()

        # Calculate advantages
        matchups = []
        for play_type in player_types:
            if play_type in opp_types:
                player_ppp = player_types[play_type]['ppp']
                player_ppg = player_types[play_type]['ppg']
                player_poss_pg = player_types[play_type]['poss_pg']
                opp_ppp = opp_types[play_type]['ppp']
                league_ppp = league_avg.get(play_type, {}).get('ppp', 1.0)

                # Apply minimum sample size filter
                if player_poss_pg < self.MIN_POSS_PER_GAME:
                    continue

                # Calculate advantages
                advantage_vs_defense = player_ppp - opp_ppp
                player_vs_league = player_ppp - league_ppp
                defense_vs_league = opp_ppp - league_ppp

                # Get team rank
                team_rank = self.get_team_rank(opponent_team_id, play_type, is_shooting=False)

                matchups.append({
                    'play_type': play_type,
                    'player_ppp': player_ppp,
                    'opp_ppp': opp_ppp,
                    'league_avg': league_ppp,
                    'advantage': advantage_vs_defense,
                    'player_vs_league': player_vs_league,
                    'defense_vs_league': defense_vs_league,
                    'player_ppg': player_ppg,
                    'player_poss_pg': player_poss_pg,
                    'team_rank': team_rank,
                    'significance': abs(advantage_vs_defense) * player_ppg
                })

        # Sort by significance
        matchups.sort(key=lambda x: x['significance'], reverse=True)
        return matchups

    def analyze_assist_zones(self, player_id: int, opponent_team_id: int) -> List[Dict]:
        """
        Compare player assist zones vs opponent defensive zones.

        Args:
            player_id: NBA API player ID
            opponent_team_id: Opponent team ID

        Returns:
            List of assist zone matchup dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get player assist zones
        cursor.execute("""
            SELECT zone_name, assists, ast_fgm, ast_fga
            FROM player_assist_zones
            WHERE player_id = ? AND season = ?
        """, (player_id, self.season))

        player_zones = {row[0]: {'assists': row[1], 'ast_fgm': row[2], 'ast_fga': row[3]}
                        for row in cursor.fetchall()}

        # Get opponent defensive zones
        cursor.execute("""
            SELECT zone_name, opp_fg_pct
            FROM team_defensive_zones
            WHERE team_id = ? AND season = ?
        """, (opponent_team_id, self.season))

        opp_zones = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        # Get league averages
        league_avg = self.get_league_average_shooting()

        # Calculate insights
        matchups = []
        for zone_name in player_zones:
            if zone_name in opp_zones:
                assists = player_zones[zone_name]['assists']
                ast_fga = player_zones[zone_name]['ast_fga']

                # Apply minimum sample size filter
                if assists < self.MIN_ASSISTS_TOTAL:
                    continue

                ast_fgm = player_zones[zone_name]['ast_fgm']
                ast_fg_pct = ast_fgm / ast_fga if ast_fga > 0 else 0
                opp_fg_pct = opp_zones[zone_name]
                league_pct = league_avg.get(zone_name, 0.40)

                # How much better are assisted shots than opponent typically allows
                advantage = ast_fg_pct - opp_fg_pct

                # Get team rank
                team_rank = self.get_team_rank(opponent_team_id, zone_name, is_shooting=True)

                # Calculate confidence interval
                ci_lower, ci_upper = self.calculate_confidence_interval(ast_fg_pct, ast_fga)

                matchups.append({
                    'zone': zone_name,
                    'assists': assists,
                    'ast_fg_pct': ast_fg_pct,
                    'opp_fg_pct': opp_fg_pct,
                    'league_avg': league_pct,
                    'advantage': advantage,
                    'team_rank': team_rank,
                    'total_attempts': ast_fga,
                    'ci_lower': ci_lower,
                    'ci_upper': ci_upper,
                    'significance': abs(advantage) * assists
                })

        matchups.sort(key=lambda x: x['significance'], reverse=True)
        return matchups

    def analyze_game(self, game: Dict, min_advantage: float = 0.05) -> Dict:
        """
        Analyze a single game for matchup advantages.

        Args:
            game: Game dictionary with visitor/home team info
            min_advantage: Minimum advantage threshold to report

        Returns:
            Dictionary with matchup analysis
        """
        print(f"\n{'='*100}")
        print(f"{game['visitor']['name']} @ {game['home']['name']}")
        print(f"Status: {game['status']}")
        print(f"{'='*100}\n")

        analysis = {
            'game': game,
            'visitor_matchups': [],
            'home_matchups': []
        }

        # Analyze visitor team players
        print(f"Analyzing {game['visitor']['name']} key players...")
        visitor_players = self.get_team_key_players(game['visitor']['id'])

        for player in visitor_players:
            print(f"\n  {player['name']} ({player['ppg']:.1f} ppg, {player['apg']:.1f} apg)")

            # Shooting zones
            shooting = self.analyze_shooting_zones(player['id'], game['home']['id'])
            significant_shooting = [s for s in shooting if abs(s['advantage']) >= min_advantage]

            # Play types
            play_types = self.analyze_play_types(player['id'], game['home']['id'])
            significant_play_types = [p for p in play_types if abs(p['advantage']) >= min_advantage]

            # Assist zones
            assist_zones = self.analyze_assist_zones(player['id'], game['home']['id'])
            significant_assists = [a for a in assist_zones if abs(a['advantage']) >= min_advantage]

            if significant_shooting:
                print(f"    Shooting Zone Advantages:")
                for s in significant_shooting[:3]:  # Top 3
                    sign = "✅" if s['advantage'] > 0 else "⚠️"
                    rank_str = f"Rank {s['team_rank']}" if s['team_rank'] else "N/A"
                    ci_width = s['ci_upper'] - s['ci_lower']
                    confidence = "High" if ci_width < 0.15 else "Med" if ci_width < 0.30 else "Low"

                    print(f"       {sign} {s['zone']:20} | Player: {s['player_fg_pct']:.1%} | Opp: {s['opp_fg_pct']:.1%} (Lg: {s['league_avg']:.1%}) | Diff: {s['advantage']:+.1%}")
                    print(f"          Defense {rank_str} | {s['player_fga']:.1f} FGA/g | Confidence: {confidence} | CI: [{s['ci_lower']:.1%}, {s['ci_upper']:.1%}]")

            if significant_play_types:
                print(f"    Play Type Advantages:")
                for p in significant_play_types[:3]:  # Top 3
                    sign = "✅" if p['advantage'] > 0 else "⚠️"
                    rank_str = f"Rank {p['team_rank']}" if p['team_rank'] else "N/A"

                    print(f"       {sign} {p['play_type']:15} | Player: {p['player_ppp']:.2f} PPP | Opp: {p['opp_ppp']:.2f} (Lg: {p['league_avg']:.2f}) | Diff: {p['advantage']:+.2f}")
                    print(f"          Defense {rank_str} | {p['player_ppg']:.1f} ppg | {p['player_poss_pg']:.1f} poss/g from this type")

            if significant_assists and player['apg'] >= 3.0:  # Only show for good passers
                print(f"    Assist Zone Opportunities:")
                for a in significant_assists[:3]:  # Top 3
                    sign = "✅" if a['advantage'] > 0 else "⚠️"
                    rank_str = f"Rank {a['team_rank']}" if a['team_rank'] else "N/A"
                    ci_width = a['ci_upper'] - a['ci_lower']
                    confidence = "High" if ci_width < 0.15 else "Med" if ci_width < 0.30 else "Low"

                    print(f"       {sign} {a['zone']:20} | Ast FG%: {a['ast_fg_pct']:.1%} | Opp: {a['opp_fg_pct']:.1%} (Lg: {a['league_avg']:.1%}) | Diff: {a['advantage']:+.1%}")
                    print(f"          Defense {rank_str} | {a['assists']:.0f} assists | Confidence: {confidence}")

            analysis['visitor_matchups'].append({
                'player': player,
                'shooting': significant_shooting,
                'play_types': significant_play_types,
                'assists': significant_assists
            })

        # Analyze home team players
        print(f"\nAnalyzing {game['home']['name']} key players...")
        home_players = self.get_team_key_players(game['home']['id'])

        for player in home_players:
            print(f"\n  {player['name']} ({player['ppg']:.1f} ppg, {player['apg']:.1f} apg)")

            # Shooting zones
            shooting = self.analyze_shooting_zones(player['id'], game['visitor']['id'])
            significant_shooting = [s for s in shooting if abs(s['advantage']) >= min_advantage]

            # Play types
            play_types = self.analyze_play_types(player['id'], game['visitor']['id'])
            significant_play_types = [p for p in play_types if abs(p['advantage']) >= min_advantage]

            # Assist zones
            assist_zones = self.analyze_assist_zones(player['id'], game['visitor']['id'])
            significant_assists = [a for a in assist_zones if abs(a['advantage']) >= min_advantage]

            if significant_shooting:
                print(f"    Shooting Zone Advantages:")
                for s in significant_shooting[:3]:  # Top 3
                    sign = "✅" if s['advantage'] > 0 else "⚠️"
                    rank_str = f"Rank {s['team_rank']}" if s['team_rank'] else "N/A"
                    ci_width = s['ci_upper'] - s['ci_lower']
                    confidence = "High" if ci_width < 0.15 else "Med" if ci_width < 0.30 else "Low"

                    print(f"       {sign} {s['zone']:20} | Player: {s['player_fg_pct']:.1%} | Opp: {s['opp_fg_pct']:.1%} (Lg: {s['league_avg']:.1%}) | Diff: {s['advantage']:+.1%}")
                    print(f"          Defense {rank_str} | {s['player_fga']:.1f} FGA/g | Confidence: {confidence} | CI: [{s['ci_lower']:.1%}, {s['ci_upper']:.1%}]")

            if significant_play_types:
                print(f"    Play Type Advantages:")
                for p in significant_play_types[:3]:  # Top 3
                    sign = "✅" if p['advantage'] > 0 else "⚠️"
                    rank_str = f"Rank {p['team_rank']}" if p['team_rank'] else "N/A"

                    print(f"       {sign} {p['play_type']:15} | Player: {p['player_ppp']:.2f} PPP | Opp: {p['opp_ppp']:.2f} (Lg: {p['league_avg']:.2f}) | Diff: {p['advantage']:+.2f}")
                    print(f"          Defense {rank_str} | {p['player_ppg']:.1f} ppg | {p['player_poss_pg']:.1f} poss/g from this type")

            if significant_assists and player['apg'] >= 3.0:
                print(f"    Assist Zone Opportunities:")
                for a in significant_assists[:3]:  # Top 3
                    sign = "✅" if a['advantage'] > 0 else "⚠️"
                    rank_str = f"Rank {a['team_rank']}" if a['team_rank'] else "N/A"
                    ci_width = a['ci_upper'] - a['ci_lower']
                    confidence = "High" if ci_width < 0.15 else "Med" if ci_width < 0.30 else "Low"

                    print(f"       {sign} {a['zone']:20} | Ast FG%: {a['ast_fg_pct']:.1%} | Opp: {a['opp_fg_pct']:.1%} (Lg: {a['league_avg']:.1%}) | Diff: {a['advantage']:+.1%}")
                    print(f"          Defense {rank_str} | {a['assists']:.0f} assists | Confidence: {confidence}")

            analysis['home_matchups'].append({
                'player': player,
                'shooting': significant_shooting,
                'play_types': significant_play_types,
                'assists': significant_assists
            })

        return analysis

    def run_analysis(self, game_date: Optional[str] = None, min_advantage: float = 0.05):
        """
        Run matchup analysis for all games on a given date.

        Args:
            game_date: Optional date in MM/DD/YYYY format
            min_advantage: Minimum advantage threshold to report (default: 0.05 = 5%)
        """
        # Get games
        games = self.get_todays_games(game_date)

        if not games:
            print("No games scheduled for this date.")
            return

        print(f"\nNBA MATCHUP ANALYSIS")
        print(f"Date: {game_date or date.today().strftime('%m/%d/%Y')}")
        print(f"Games: {len(games)}")
        print(f"Minimum Advantage Threshold: {min_advantage:.1%}")
        print(f"\nMinimum Sample Sizes: {self.MIN_FGA_PER_GAME} FGA/g | {self.MIN_POSS_PER_GAME} Poss/g | {self.MIN_ASSISTS_TOTAL} assists")
        print(f"\nLegend:")
        print(f"  • Rank 1-10 = Elite defense | Rank 11-20 = Average | Rank 21-30 = Poor defense")
        print(f"  • Confidence: High (narrow CI) = reliable | Low (wide CI) = small sample, less reliable")
        print(f"  • (Lg: X.X%) = League average for comparison")

        # Analyze each game
        all_analyses = []
        for game in games:
            try:
                analysis = self.analyze_game(game, min_advantage)
                all_analyses.append(analysis)
            except Exception as e:
                print(f"\n Error analyzing {game['visitor']['name']} @ {game['home']['name']}: {e}")
                import traceback
                traceback.print_exc()
                continue

        print(f"\n{'='*100}")
        print("Analysis complete!")
        print(f"{'='*100}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Analyze NBA matchups for today\'s games (Enhanced)')
    parser.add_argument('--date', type=str, help='Date in MM/DD/YYYY format (default: today)')
    parser.add_argument('--min-advantage', type=float, default=0.05,
                        help='Minimum advantage threshold (default: 0.05 = 5%%)')
    parser.add_argument('--db', type=str, default='nba_stats.db',
                        help='Path to database file (default: nba_stats.db)')

    args = parser.parse_args()

    analyzer = MatchupAnalyzer(db_path=args.db)
    analyzer.run_analysis(game_date=args.date, min_advantage=args.min_advantage)


if __name__ == '__main__':
    main()
