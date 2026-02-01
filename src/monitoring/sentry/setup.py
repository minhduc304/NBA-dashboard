"""
Sentry Setup and Context Management

Initializes Sentry SDK and provides context enrichment helpers.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import MonitoringConfig

logger = logging.getLogger(__name__)

# Track initialization state
_sentry_initialized = False


def init_sentry(config: Optional[MonitoringConfig] = None) -> bool:
    """
    Initialize Sentry SDK.

    Args:
        config: MonitoringConfig with DSN

    Returns:
        True if initialized successfully
    """
    global _sentry_initialized

    if _sentry_initialized:
        return True

    config = config or MonitoringConfig.from_env()

    if not config.sentry_enabled:
        logger.debug("Sentry not configured, skipping initialization")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        # Configure logging integration
        logging_integration = LoggingIntegration(
            level=logging.INFO,  # Capture INFO and above as breadcrumbs
            event_level=logging.ERROR,  # Send ERROR and above as events
        )

        sentry_sdk.init(
            dsn=config.sentry_dsn,
            environment=config.sentry_environment,
            traces_sample_rate=config.sentry_traces_sample_rate,
            integrations=[logging_integration],
            # Send relevant context
            send_default_pii=False,
            attach_stacktrace=True,
            # Performance monitoring
            enable_tracing=True,
        )

        # Set common tags
        sentry_sdk.set_tag("job_name", config.job_name)
        sentry_sdk.set_tag("region", config.region)

        _sentry_initialized = True
        logger.debug("Sentry initialized successfully")
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed, Sentry tracking disabled")
        return False
    except Exception as e:
        logger.error("Failed to initialize Sentry: %s", e)
        return False


def set_pipeline_context(
    job_name: str,
    step_name: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_steps: Optional[List[str]] = None,
) -> None:
    """
    Set pipeline execution context for Sentry.

    Args:
        job_name: Pipeline job name
        step_name: Current step being executed
        started_at: Pipeline start time
        completed_steps: List of completed step names
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.set_context("pipeline", {
            "job_name": job_name,
            "current_step": step_name,
            "started_at": started_at.isoformat() if started_at else None,
            "completed_steps": completed_steps or [],
            "steps_completed": len(completed_steps) if completed_steps else 0,
        })

        if step_name:
            sentry_sdk.set_tag("pipeline_step", step_name)

    except Exception as e:
        logger.debug("Failed to set pipeline context: %s", e)


def set_scraper_context(
    scraper_name: str,
    api_key_index: Optional[int] = None,
    quota_remaining: Optional[int] = None,
    keys_total: int = 1,
) -> None:
    """
    Set scraper context for API-related errors.

    Args:
        scraper_name: Name of the scraper (odds_api, underdog)
        api_key_index: Current API key index (for rotation)
        quota_remaining: Remaining API quota
        keys_total: Total number of API keys
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.set_context("api_status", {
            "scraper": scraper_name,
            "key_index": api_key_index,
            "quota_remaining": quota_remaining,
            "keys_total": keys_total,
            "keys_exhausted": api_key_index if api_key_index is not None else 0,
        })

        sentry_sdk.set_tag("scraper", scraper_name)

    except Exception as e:
        logger.debug("Failed to set scraper context: %s", e)


def set_training_context(
    stat_type: str,
    model_type: str = "classifier",
    sample_size: Optional[int] = None,
    feature_count: Optional[int] = None,
    attempt: int = 1,
) -> None:
    """
    Set training context for model training errors.

    Args:
        stat_type: Stat type being trained (points, rebounds, etc.)
        model_type: Model type (classifier, regressor)
        sample_size: Training sample size
        feature_count: Number of features
        attempt: Training attempt number
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.set_context("training", {
            "stat_type": stat_type,
            "model_type": model_type,
            "sample_size": sample_size,
            "feature_count": feature_count,
            "attempt": attempt,
        })

        sentry_sdk.set_tag("stat_type", stat_type)
        sentry_sdk.set_tag("model", model_type)

    except Exception as e:
        logger.debug("Failed to set training context: %s", e)


def add_breadcrumb(
    message: str,
    category: str = "pipeline",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Add a breadcrumb to the current Sentry scope.

    Breadcrumbs help trace the sequence of events leading to an error.

    Args:
        message: Breadcrumb message
        category: Category (pipeline, data, io, api)
        level: Level (debug, info, warning, error)
        data: Additional data
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data,
        )

    except Exception as e:
        logger.debug("Failed to add breadcrumb: %s", e)


def capture_exception(
    exception: Exception,
    level: str = "error",
    tags: Optional[Dict[str, str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Capture an exception and send to Sentry.

    Args:
        exception: The exception to capture
        level: Severity level (error, warning, info)
        tags: Additional tags
        extra: Additional context data

    Returns:
        Sentry event ID if captured, None otherwise
    """
    if not _sentry_initialized:
        return None

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.level = level

            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)

            if extra:
                for key, value in extra.items():
                    scope.set_extra(key, value)

            event_id = sentry_sdk.capture_exception(exception)
            return event_id

    except Exception as e:
        logger.debug("Failed to capture exception: %s", e)
        return None


def capture_message(
    message: str,
    level: str = "info",
    tags: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Capture a message and send to Sentry.

    Useful for non-exception events like warnings.

    Args:
        message: Message to capture
        level: Severity level
        tags: Additional tags

    Returns:
        Sentry event ID if captured, None otherwise
    """
    if not _sentry_initialized:
        return None

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.level = level

            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)

            event_id = sentry_sdk.capture_message(message)
            return event_id

    except Exception as e:
        logger.debug("Failed to capture message: %s", e)
        return None


def start_transaction(
    name: str,
    op: str = "pipeline",
) -> Any:
    """
    Start a Sentry transaction for performance monitoring.

    Args:
        name: Transaction name
        op: Operation type

    Returns:
        Transaction object (or None if Sentry not initialized)
    """
    if not _sentry_initialized:
        return None

    try:
        import sentry_sdk

        return sentry_sdk.start_transaction(name=name, op=op)

    except Exception as e:
        logger.debug("Failed to start transaction: %s", e)
        return None
