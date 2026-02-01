"""
Monitoring and Notification System for NBA Stats Pipeline

Provides:
- Rich Slack notifications with Block Kit formatting
- Sentry error tracking with context
- Pipeline result collection and reporting
"""

from .config import MonitoringConfig
from .types import (
    PipelineResult,
    StepResult,
    StepStatus,
    PipelineStatus,
    ModelPerformance,
    APIHealth,
)
from .decorators import (
    capture_errors,
    track_performance,
    StepTracker,
)
from .slack import SlackNotifier
from .sentry import (
    init_sentry,
    set_pipeline_context,
    add_breadcrumb,
    capture_exception,
)

__all__ = [
    # Config
    'MonitoringConfig',
    # Types
    'PipelineResult',
    'StepResult',
    'StepStatus',
    'PipelineStatus',
    'ModelPerformance',
    'APIHealth',
    # Decorators
    'capture_errors',
    'track_performance',
    'StepTracker',
    # Slack
    'SlackNotifier',
    # Sentry
    'init_sentry',
    'set_pipeline_context',
    'add_breadcrumb',
    'capture_exception',
]
