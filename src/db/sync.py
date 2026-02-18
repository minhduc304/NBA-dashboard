"""
Database sync between local and cloud (GCS).

Merges cloud-managed tables into the local DB without overwriting
local-only tables (shooting zones, assist zones, play types, etc.).
"""

import json
import logging
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import google.auth
from google.cloud import storage as gcs
from google.oauth2 import credentials as oauth2_credentials

from src.config import get_db_path

logger = logging.getLogger(__name__)

GCS_BUCKET = "nba-stats-pipeline-data"

# Tables managed by the cloud pipeline and their merge strategy.
# "replace" = INSERT OR REPLACE (cloud wins on PK match)
# "ignore"  = INSERT OR IGNORE  (dedup via UNIQUE constraint, exclude id)
CLOUD_TABLES: dict[str, str] = {
    # Composite PK tables
    "player_game_logs": "replace",
    "player_rolling_stats": "replace",
    "team_pace": "replace",
    "model_versions": "replace",
    # AUTOINCREMENT tables
    "player_injuries": "ignore",
    "all_props": "ignore",
    "underdog_props": "ignore",
    "prizepicks_props": "ignore",
    "odds_api_props": "ignore",
    "prop_outcomes": "ignore",
    "paper_trades": "ignore",
    "prediction_log": "ignore",
}


@dataclass
class MergeResult:
    table: str
    strategy: str
    cloud_rows: int = 0
    local_before: int = 0
    local_after: int = 0
    new_rows: int = 0
    skipped_columns: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def status(self) -> str:
        if self.error:
            return "ERROR"
        if self.new_rows > 0:
            return "UPDATED"
        return "OK"


@dataclass
class SyncReport:
    results: list[MergeResult] = field(default_factory=list)
    backup_path: Optional[str] = None
    cloud_db_path: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    dry_run: bool = False

    @property
    def total_new_rows(self) -> int:
        return sum(r.new_rows for r in self.results)

    @property
    def tables_updated(self) -> int:
        return sum(1 for r in self.results if r.new_rows > 0)

    @property
    def errors(self) -> list[MergeResult]:
        return [r for r in self.results if r.error]


def _get_gcs_client() -> gcs.Client:
    """Create a GCS client.

    Tries Application Default Credentials first, then falls back to
    gcloud CLI user credentials (legacy adc.json) so that users who
    have run ``gcloud auth login`` don't need a separate ADC setup.
    """
    try:
        creds, project = google.auth.default()
        return gcs.Client(credentials=creds, project=project)
    except google.auth.exceptions.DefaultCredentialsError:
        pass

    # Fall back to gcloud CLI legacy credentials
    creds = _load_gcloud_user_credentials()
    if creds:
        return gcs.Client(credentials=creds, project="nba-stats-pipeline")

    raise google.auth.exceptions.DefaultCredentialsError(
        "No GCS credentials found. Run: gcloud auth application-default login"
    )


def _load_gcloud_user_credentials() -> Optional[oauth2_credentials.Credentials]:
    """Load OAuth2 credentials from gcloud CLI legacy adc.json files."""
    gcloud_dir = Path.home() / ".config" / "gcloud" / "legacy_credentials"
    if not gcloud_dir.exists():
        return None

    # Find the first account's adc.json
    for account_dir in gcloud_dir.iterdir():
        adc_file = account_dir / "adc.json"
        if adc_file.exists():
            data = json.loads(adc_file.read_text())
            creds = oauth2_credentials.Credentials.from_authorized_user_info(data)
            logger.debug("Using gcloud credentials for %s", account_dir.name)
            return creds

    return None


class DatabaseSyncer:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.backup_dir = self.project_root / "data" / "backups"
        self.data_dir = self.project_root / "data"

    def pull(self, dry_run: bool = False, skip_models: bool = False) -> SyncReport:
        """Download cloud DB and merge cloud-managed tables into local."""
        report = SyncReport(started_at=datetime.now(), dry_run=dry_run)

        # Download cloud DB to temp file
        cloud_db_path = self._download_from_gcs()
        report.cloud_db_path = str(cloud_db_path)

        if dry_run:
            report.results = self._preview_merge(cloud_db_path)
        else:
            # Backup local DB first
            report.backup_path = self._backup_local_db()
            report.results = self._merge_tables(cloud_db_path)

        # Clean up temp cloud DB
        if cloud_db_path.exists():
            cloud_db_path.unlink()

        # Sync trained models
        if not dry_run and not skip_models:
            self._sync_models()

        report.finished_at = datetime.now()
        return report

    def push(self) -> None:
        """Upload local DB to GCS."""
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Local DB not found: {self.db_path}")

        client = _get_gcs_client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob("nba_stats.db")

        logger.info("Uploading %s to gs://%s/nba_stats.db", self.db_path, GCS_BUCKET)
        blob.upload_from_filename(self.db_path)
        logger.info("Upload complete")

    def status(self) -> dict[str, int]:
        """Return row counts for cloud-managed tables in the local DB."""
        counts = {}
        if not Path(self.db_path).exists():
            return counts

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get list of tables that actually exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}

        for table in CLOUD_TABLES:
            if table in existing:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                counts[table] = cursor.fetchone()[0]
            else:
                counts[table] = 0

        conn.close()
        return counts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _merge_tables(self, cloud_db_path: Path) -> list[MergeResult]:
        """Attach cloud DB and merge each cloud-managed table."""
        results = []
        conn = sqlite3.connect(self.db_path)
        conn.execute("ATTACH DATABASE ? AS cloud", (str(cloud_db_path),))

        # Get tables that exist in the cloud DB
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM cloud.sqlite_master WHERE type='table'")
        cloud_tables = {row[0] for row in cursor.fetchall()}

        # Get tables that exist in the local DB
        cursor.execute("SELECT name FROM main.sqlite_master WHERE type='table'")
        local_tables = {row[0] for row in cursor.fetchall()}

        for table, strategy in CLOUD_TABLES.items():
            result = MergeResult(table=table, strategy=strategy)

            if table not in cloud_tables:
                result.error = "not in cloud DB"
                results.append(result)
                continue

            if table not in local_tables:
                result.error = "not in local DB"
                results.append(result)
                continue

            try:
                # Count rows before
                cursor.execute(f"SELECT COUNT(*) FROM main.[{table}]")
                result.local_before = cursor.fetchone()[0]

                cursor.execute(f"SELECT COUNT(*) FROM cloud.[{table}]")
                result.cloud_rows = cursor.fetchone()[0]

                # Get column intersection
                cols, skipped = self._get_column_intersection(cursor, table, strategy)
                result.skipped_columns = skipped

                if not cols:
                    result.error = "no overlapping columns"
                    results.append(result)
                    continue

                col_list = ", ".join(f"[{c}]" for c in cols)
                verb = "OR REPLACE" if strategy == "replace" else "OR IGNORE"

                cursor.execute(
                    f"INSERT {verb} INTO main.[{table}] ({col_list}) "
                    f"SELECT {col_list} FROM cloud.[{table}]"
                )

                # Count rows after
                cursor.execute(f"SELECT COUNT(*) FROM main.[{table}]")
                result.local_after = cursor.fetchone()[0]
                result.new_rows = result.local_after - result.local_before

            except Exception as e:
                result.error = str(e)

            results.append(result)

        conn.commit()
        conn.execute("DETACH DATABASE cloud")
        conn.close()

        return results

    def _preview_merge(self, cloud_db_path: Path) -> list[MergeResult]:
        """Dry-run: attach cloud DB, count rows, no writes."""
        results = []
        conn = sqlite3.connect(self.db_path)
        conn.execute("ATTACH DATABASE ? AS cloud", (str(cloud_db_path),))

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM cloud.sqlite_master WHERE type='table'")
        cloud_tables = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT name FROM main.sqlite_master WHERE type='table'")
        local_tables = {row[0] for row in cursor.fetchall()}

        for table, strategy in CLOUD_TABLES.items():
            result = MergeResult(table=table, strategy=strategy)

            if table not in cloud_tables:
                result.error = "not in cloud DB"
                results.append(result)
                continue

            if table not in local_tables:
                result.error = "not in local DB"
                results.append(result)
                continue

            try:
                cursor.execute(f"SELECT COUNT(*) FROM main.[{table}]")
                result.local_before = cursor.fetchone()[0]
                result.local_after = result.local_before  # unchanged in dry-run

                cursor.execute(f"SELECT COUNT(*) FROM cloud.[{table}]")
                result.cloud_rows = cursor.fetchone()[0]

                _, skipped = self._get_column_intersection(cursor, table, strategy)
                result.skipped_columns = skipped

            except Exception as e:
                result.error = str(e)

            results.append(result)

        conn.execute("DETACH DATABASE cloud")
        conn.close()
        return results

    def _get_column_intersection(
        self, cursor: sqlite3.Cursor, table: str, strategy: str
    ) -> tuple[list[str], list[str]]:
        """Return (shared_columns, skipped_columns) for a table.

        For 'ignore' strategy, the 'id' column is excluded so that
        AUTOINCREMENT tables dedup via their UNIQUE constraints.
        """
        cursor.execute(f"PRAGMA main.table_info([{table}])")
        local_cols = {row[1] for row in cursor.fetchall()}

        cursor.execute(f"PRAGMA cloud.table_info([{table}])")
        cloud_cols = {row[1] for row in cursor.fetchall()}

        shared = local_cols & cloud_cols

        # For autoincrement tables, exclude the id column
        if strategy == "ignore":
            shared.discard("id")

        skipped = sorted(cloud_cols - local_cols)
        if skipped:
            logger.warning(
                "Table %s: cloud has columns not in local (skipped): %s",
                table,
                skipped,
            )

        return sorted(shared), skipped

    def _backup_local_db(self) -> Optional[str]:
        """Copy local DB to backups dir, keep last 7."""
        if not Path(self.db_path).exists():
            return None

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"nba_stats_{timestamp}.db"
        shutil.copy2(self.db_path, backup_path)
        logger.info("Backed up to %s", backup_path)

        # Prune old backups
        backups = sorted(self.backup_dir.glob("nba_stats_*.db"), reverse=True)
        for old in backups[7:]:
            old.unlink()
            logger.debug("Removed old backup: %s", old)

        return str(backup_path)

    def _download_from_gcs(self) -> Path:
        """Download cloud DB to a temp file in data/."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.data_dir / "cloud_nba_stats.db"

        client = _get_gcs_client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob("nba_stats.db")

        logger.info("Downloading gs://%s/nba_stats.db ...", GCS_BUCKET)
        blob.download_to_filename(str(tmp_path))
        logger.info("Downloaded cloud DB (%s)", _human_size(tmp_path))
        return tmp_path

    def _sync_models(self) -> None:
        """Sync trained model files from GCS."""
        models_dir = self.project_root / "trained_models"

        client = _get_gcs_client()
        bucket = client.bucket(GCS_BUCKET)

        # List model blobs in the cloud
        blobs = list(bucket.list_blobs(prefix="trained_models/"))
        model_blobs = [b for b in blobs if b.name.endswith(".joblib")]

        if not model_blobs:
            logger.info("No trained models in cloud, skipping")
            return

        models_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Syncing %d trained models...", len(model_blobs))

        for blob in model_blobs:
            # blob.name is "trained_models/foo.joblib" — extract filename
            filename = Path(blob.name).name
            local_path = models_dir / filename
            blob.download_to_filename(str(local_path))
            logger.debug("Downloaded %s", filename)

        logger.info("Models synced")


def _human_size(path: Path) -> str:
    """Return human-readable file size."""
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"