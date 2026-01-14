from dataclasses import dataclass
import os

@dataclass 
class APIConfig:
    timeout: int = 30
    delay: float = 0.6
    max_retries: int = 3

@dataclass
class Config:
    season: str = '2025-26'
    db_path: str = 'data/nba_stats.db'
    api: APIConfig = None

    def __post_init__(self):
        if self.api is None:
            self.api = APIConfig()
    
    @classmethod
    def from_env(cls) -> 'Config':
        return cls(
            season = os.getenv('NBA_SEASON', '2025-26'),
            db_path = os.getenv('DB_PATH', 'data/nba_stats.db'),
            api=APIConfig(
                timeout = int(os.getenv('API_TIMEOUT', 30)),
                delay = float(os.getenv('API_DELAY', 0,6)),
            )
        )
    
