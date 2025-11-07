"""
Verify data in the database
"""
import sqlite3
import pandas as pd

def verify_data(db_path='nba_stats.db'):
    conn = sqlite3.connect(db_path)

    # Get all data
    df = pd.read_sql_query("SELECT * FROM player_stats", conn)

    conn.close()

    if df.empty:
        print("No data in database!")
        return

    print(f"Found {len(df)} player(s) in database\n")

    for _, row in df.iterrows():
        print("=" * 70)
        print(f"Player: {row['player_name']} (ID: {row['player_id']})")
        print(f"Season: {row['season']} | Games Played: {row['games_played']}")
        print("=" * 70)

        print("\nBASIC STATS (Must-have):")
        print(f"  Points: {row['points']}")
        print(f"  Assists: {row['assists']}")
        print(f"  Rebounds: {row['rebounds']}")
        print(f"  Threes Made: {row['threes_made']}")
        print(f"  Steals: {row['steals']}")
        print(f"  Blocks: {row['blocks']}")
        print(f"  Turnovers: {row['turnovers']}")
        print(f"  Fouls: {row['fouls']}")
        print(f"  FT Attempted: {row['ft_attempted']}")

        print("\nCOMBO STATS (Calculated):")
        print(f"  PTS+AST: {row['pts_plus_ast']}")
        print(f"  PTS+REB: {row['pts_plus_reb']}")
        print(f"  AST+REB: {row['ast_plus_reb']}")
        print(f"  PTS+AST+REB: {row['pts_plus_ast_plus_reb']}")
        print(f"  STL+BLK: {row['steals_plus_blocks']}")

        print("\nACHIEVEMENTS:")
        print(f"  Double Doubles: {row['double_doubles']}")
        print(f"  Triple Doubles: {row['triple_doubles']}")

        print("\nQUARTER/HALF STATS:")
        print(f"  Q1 Points: {row['q1_points']}")
        print(f"  Q1 Assists: {row['q1_assists']}")
        print(f"  Q1 Rebounds: {row['q1_rebounds']}")
        print(f"  First Half Points: {row['first_half_points']}")

        print(f"\nLast Updated: {row['last_updated']}")
        print()

if __name__ == "__main__":
    verify_data()
