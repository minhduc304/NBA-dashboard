#!/usr/bin/env python3
"""
Query and display player play type statistics
"""

import sqlite3
import pandas as pd
import argparse


def query_player_play_types(player_name, db_path='nba_stats.db'):
    """Query play type breakdown for a specific player."""
    conn = sqlite3.connect(db_path)

    query = """
    SELECT
        ps.player_name,
        ppt.play_type,
        ppt.points_per_game,
        ppt.poss_per_game,
        ppt.ppp,
        ppt.fg_pct,
        ppt.pct_of_total_points,
        ppt.games_played
    FROM player_play_types ppt
    JOIN player_stats ps ON ppt.player_id = ps.player_id
    WHERE ps.player_name = ?
    ORDER BY ppt.points_per_game DESC
    """

    df = pd.read_sql_query(query, conn, params=(player_name,))
    conn.close()

    if df.empty:
        print(f"\nNo play type data found for {player_name}")
        print("Have you run: python update_stats.py --collect-play-types ?")
        return

    # Fix games_played if it's stored as bytes
    games_played = df.iloc[0]['games_played']
    if isinstance(games_played, bytes):
        games_played = int.from_bytes(games_played, byteorder='little') if len(games_played) > 0 else 0
    else:
        games_played = int(games_played) if games_played is not None else 0

    total_ppg = df['points_per_game'].sum()

    print(f"\n{player_name} - Play Type Breakdown")
    print("=" * 100)
    print(f"Games Played: {games_played}")
    print(f"Total PPG from Play Types: {total_ppg:.2f}")
    print("=" * 100)
    print()

    # Display table
    display_df = df[['play_type', 'points_per_game', 'poss_per_game', 'ppp', 'fg_pct', 'pct_of_total_points']].copy()
    display_df.columns = ['Play Type', 'PPG', 'Poss/G', 'PPP', 'FG%', '% of Pts']
    display_df['FG%'] = (display_df['FG%'] * 100).round(1)
    display_df['% of Pts'] = display_df['% of Pts'].round(1)
    display_df['PPG'] = display_df['PPG'].round(2)
    display_df['Poss/G'] = display_df['Poss/G'].round(1)
    display_df['PPP'] = display_df['PPP'].round(3)

    print(display_df.to_string(index=False))
    print()

    # Visual breakdown
    print("\nVisual Breakdown:")
    print("-" * 100)
    for _, row in df.iterrows():
        bar_length = int(row['pct_of_total_points'] / 2)
        bar = "█" * bar_length
        print(f"{row['play_type']:18} {bar} {row['pct_of_total_points']:5.1f}% ({row['points_per_game']:5.2f} ppg)")


def compare_players(player_names, db_path='nba_stats.db'):
    """Compare play type breakdowns for multiple players."""
    conn = sqlite3.connect(db_path)

    query = """
    SELECT
        ps.player_name,
        ppt.play_type,
        ppt.points_per_game,
        ppt.pct_of_total_points
    FROM player_play_types ppt
    JOIN player_stats ps ON ppt.player_id = ps.player_id
    WHERE ps.player_name IN ({})
    ORDER BY ps.player_name, ppt.points_per_game DESC
    """.format(','.join('?' * len(player_names)))

    df = pd.read_sql_query(query, conn, params=player_names)
    conn.close()

    if df.empty:
        print("\nNo data found for these players")
        return

    print(f"\nPlay Type Comparison")
    print("=" * 120)

    # Pivot table for comparison
    pivot = df.pivot(index='play_type', columns='player_name', values='pct_of_total_points')
    pivot = pivot.fillna(0).round(1)
    print(pivot.to_string())
    print()


def top_players_by_playtype(play_type, limit=10, db_path='nba_stats.db'):
    """Show top players for a specific play type by efficiency."""
    conn = sqlite3.connect(db_path)

    query = """
    SELECT
        ps.player_name,
        ppt.points_per_game,
        ppt.poss_per_game,
        ppt.ppp,
        ppt.fg_pct,
        ppt.pct_of_total_points
    FROM player_play_types ppt
    JOIN player_stats ps ON ppt.player_id = ps.player_id
    WHERE ppt.play_type = ?
    ORDER BY ppt.ppp DESC
    LIMIT ?
    """

    df = pd.read_sql_query(query, conn, params=(play_type, limit))
    conn.close()

    if df.empty:
        print(f"\nNo data found for play type: {play_type}")
        return

    print(f"\nTop {limit} Players by {play_type} Efficiency (PPP)")
    print("=" * 100)

    df['fg_pct'] = (df['fg_pct'] * 100).round(1)
    df['pct_of_total_points'] = df['pct_of_total_points'].round(1)
    df.columns = ['Player', 'PPG', 'Poss/G', 'PPP', 'FG%', '% of Total']

    print(df.to_string(index=False))
    print()


def list_available_play_types(db_path='nba_stats.db'):
    """List all available play types in the database."""
    conn = sqlite3.connect(db_path)

    query = "SELECT DISTINCT play_type FROM player_play_types ORDER BY play_type"
    df = pd.read_sql_query(query, conn)
    conn.close()

    print("\nAvailable Play Types:")
    print("=" * 40)
    for play_type in df['play_type']:
        print(f"  • {play_type}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Query NBA player play type statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query single player
  python query_play_types.py "Kevin Durant"

  # Compare multiple players
  python query_play_types.py --compare "Kevin Durant" "LeBron James" "Giannis Antetokounmpo"

  # Top players by play type
  python query_play_types.py --top Isolation --limit 15

  # List available play types
  python query_play_types.py --list
        """
    )

    parser.add_argument('player_name', nargs='?', help='Player name to query')
    parser.add_argument('--compare', nargs='+', help='Compare multiple players')
    parser.add_argument('--top', type=str, help='Show top players for a specific play type')
    parser.add_argument('--limit', type=int, default=10, help='Number of players to show (default: 10)')
    parser.add_argument('--list', action='store_true', help='List all available play types')

    args = parser.parse_args()

    if args.list:
        list_available_play_types()
    elif args.compare:
        compare_players(args.compare)
    elif args.top:
        top_players_by_playtype(args.top, args.limit)
    elif args.player_name:
        query_player_play_types(args.player_name)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
