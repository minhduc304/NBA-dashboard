"""
Monitoring Decorators

Provides decorators for automatic error capture and performance tracking.
"""

import functools
import logging
import time
import traceback
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from .sentry.setup import (
    add_breadcrumb,
    capture_exception,
    set_pipeline_context,
    set_scraper_context,
    set_training_context,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def capture_errors(
    step_name: Optional[str] = None,
    reraise: bool = True,
    tags: Optional[Dict[str, str]] = None,
) -> Callable[[F], F]:
    """
    Decorator to capture exceptions and send to Sentry.

    Args:
        step_name: Optional step name for context
        reraise: Whether to reraise the exception after capture
        tags: Additional tags to include

    Usage:
        @capture_errors(step_name="odds_api")
        def scrape_props():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            name = step_name or func.__name__

            # Add breadcrumb for function entry
            add_breadcrumb(
                message=f"Starting {name}",
                category="pipeline",
                level="info",
            )

            try:
                result = func(*args, **kwargs)

                # Add breadcrumb for success
                add_breadcrumb(
                    message=f"Completed {name}",
                    category="pipeline",
                    level="info",
                )

                return result

            except Exception as e:
                # Capture with context
                error_tags = {"step": name}
                if tags:
                    error_tags.update(tags)

                capture_exception(
                    exception=e,
                    tags=error_tags,
                    extra={
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                )

                if reraise:
                    raise

                return None

        return cast(F, wrapper)

    return decorator


def track_performance(
    operation_name: Optional[str] = None,
    warn_threshold_seconds: float = 60.0,
) -> Callable[[F], F]:
    """
    Decorator to track function performance.

    Args:
        operation_name: Name for the operation
        warn_threshold_seconds: Log warning if exceeds this duration

    Usage:
        @track_performance(operation_name="scrape_odds_api", warn_threshold_seconds=120)
        def scrape_props():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            name = operation_name or func.__name__
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                return result

            finally:
                duration = time.time() - start_time

                # Add timing breadcrumb
                add_breadcrumb(
                    message=f"{name} completed in {duration:.2f}s",
                    category="performance",
                    level="info",
                    data={"duration_seconds": duration},
                )

                if duration > warn_threshold_seconds:
                    logger.warning(
                        "%s took %.2f seconds (threshold: %.2f)",
                        name,
                        duration,
                        warn_threshold_seconds,
                    )

        return cast(F, wrapper)

    return decorator


def with_pipeline_context(
    job_name: str = "nba-daily-pipeline",
) -> Callable[[F], F]:
    """
    Decorator to set pipeline context before execution.

    Args:
        job_name: Pipeline job name

    Usage:
        @with_pipeline_context(job_name="nba-daily-pipeline")
        def run_pipeline():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from datetime import datetime

            set_pipeline_context(
                job_name=job_name,
                started_at=datetime.now(),
            )

            return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def with_scraper_context(
    scraper_name: str,
) -> Callable[[F], F]:
    """
    Decorator to set scraper context before execution.

    Args:
        scraper_name: Name of the scraper

    Usage:
        @with_scraper_context(scraper_name="odds_api")
        def scrape():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            set_scraper_context(scraper_name=scraper_name)
            return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def with_training_context(
    stat_type: str,
    model_type: str = "classifier",
) -> Callable[[F], F]:
    """
    Decorator to set training context before execution.

    Args:
        stat_type: Stat type being trained
        model_type: Model type

    Usage:
        @with_training_context(stat_type="points", model_type="classifier")
        def train_model():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            set_training_context(
                stat_type=stat_type,
                model_type=model_type,
            )
            return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


class StepTracker:
    """
    Context manager for tracking pipeline steps.

    Usage:
        with StepTracker("odds_api", pipeline_result) as tracker:
            result = scrape_odds_api()
            tracker.set_result(result)
    """

    def __init__(
        self,
        step_name: str,
        pipeline_result: Any = None,
        job_name: str = "nba-daily-pipeline",
    ):
        self.step_name = step_name
        self.pipeline_result = pipeline_result
        self.job_name = job_name
        self._start_time: Optional[float] = None
        self._result: Any = None
        self._error: Optional[Exception] = None
        self._traceback: Optional[str] = None

    def __enter__(self) -> "StepTracker":
        from datetime import datetime

        self._start_time = time.time()

        # Set Sentry context
        completed_steps = []
        if self.pipeline_result:
            completed_steps = [
                s.name for s in getattr(self.pipeline_result, "steps", [])
            ]

        set_pipeline_context(
            job_name=self.job_name,
            step_name=self.step_name,
            started_at=datetime.now(),
            completed_steps=completed_steps,
        )

        add_breadcrumb(
            message=f"Starting step: {self.step_name}",
            category="pipeline",
            level="info",
        )

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        from datetime import datetime
        from .types import StepResult, StepStatus

        end_time = time.time()
        duration = end_time - (self._start_time or end_time)

        if exc_val is not None:
            self._error = exc_val
            self._traceback = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))

            # Capture to Sentry
            capture_exception(
                exception=exc_val,
                tags={"step": self.step_name},
                extra={"duration_seconds": duration},
            )

            add_breadcrumb(
                message=f"Step failed: {self.step_name} - {exc_val}",
                category="pipeline",
                level="error",
            )

            # Add failed step to pipeline result
            if self.pipeline_result:
                step_result = StepResult(
                    name=self.step_name,
                    status=StepStatus.FAILED,
                    started_at=datetime.fromtimestamp(self._start_time or end_time),
                    ended_at=datetime.now(),
                    error=str(exc_val),
                    error_traceback=self._traceback,
                )
                self.pipeline_result.add_step(step_result)

            # Don't suppress the exception
            return False

        # Success
        add_breadcrumb(
            message=f"Step completed: {self.step_name}",
            category="pipeline",
            level="info",
            data={"duration_seconds": duration},
        )

        if self.pipeline_result:
            step_result = StepResult(
                name=self.step_name,
                status=StepStatus.SUCCESS,
                started_at=datetime.fromtimestamp(self._start_time or end_time),
                ended_at=datetime.now(),
                result=self._result,
            )
            self.pipeline_result.add_step(step_result)

        return False

    def set_result(self, result: Any) -> None:
        """Set the step result."""
        self._result = result
