"""
Monitoring Configuration

Loads monitoring settings from environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MonitoringConfig:
    """Configuration for monitoring services."""

    # Slack settings
    slack_webhook_url: Optional[str] = field(default=None)
    slack_notify_on_success: bool = True
    slack_notify_on_failure: bool = True

    # Sentry settings
    sentry_dsn: Optional[str] = field(default=None)
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.1

    # Alert thresholds
    odds_api_quota_warning_threshold: int = 100
    pipeline_duration_warning_seconds: int = 1800  # 30 minutes

    # Job metadata
    job_name: str = "nba-daily-pipeline"
    region: str = "us-west1"

    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        """Create config from environment variables."""
        return cls(
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
            slack_notify_on_success=os.getenv("SLACK_NOTIFY_ON_SUCCESS", "true").lower() == "true",
            slack_notify_on_failure=os.getenv("SLACK_NOTIFY_ON_FAILURE", "true").lower() == "true",
            sentry_dsn=os.getenv("SENTRY_DSN"),
            sentry_environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            sentry_traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            odds_api_quota_warning_threshold=int(os.getenv("ODDS_API_QUOTA_WARNING_THRESHOLD", "100")),
            pipeline_duration_warning_seconds=int(os.getenv("PIPELINE_DURATION_WARNING_SECONDS", "1800")),
            job_name=os.getenv("CLOUD_RUN_JOB", "nba-daily-pipeline"),
            region=os.getenv("CLOUD_RUN_REGION", "us-west1"),
        )

    @property
    def slack_enabled(self) -> bool:
        """Check if Slack notifications are configured."""
        return bool(self.slack_webhook_url)

    @property
    def sentry_enabled(self) -> bool:
        """Check if Sentry tracking is configured."""
        return bool(self.sentry_dsn)
