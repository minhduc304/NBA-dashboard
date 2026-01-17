from dataclasses import dataclass
import os

# Default database path constant
DEFAULT_DB_PATH = 'data/nba_stats.db'


def get_db_path() -> str:
    """
    Get the database path from environment variable or default.

    Uses DB_PATH environment variable if set, otherwise returns default path.
    This is the single source of truth for database path configuration.

    Returns:
        Path to the SQLite database file
    """
    return os.getenv('DB_PATH', DEFAULT_DB_PATH)


@dataclass
class APIConfig:
    timeout: int = 30
    delay: float = 0.6
    max_retries: int = 3

@dataclass
class Config:
    season: str = '2025-26'
    db_path: str = DEFAULT_DB_PATH
    api: APIConfig = None

    def __post_init__(self):
        if self.api is None:
            self.api = APIConfig()

    @classmethod
    def from_env(cls) -> 'Config':
        return cls(
            season = os.getenv('NBA_SEASON', '2025-26'),
            db_path = get_db_path(),
            api=APIConfig(
                timeout = int(os.getenv('API_TIMEOUT', 30)),
                delay = float(os.getenv('API_DELAY', 0.6)),
            )
        )
    
