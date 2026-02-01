"""
Slack Notification Module

Provides rich Block Kit formatted notifications for pipeline events.
"""

from .client import SlackNotifier
from .blocks import (
    build_pipeline_summary,
    build_error_alert,
    build_quota_warning,
)

__all__ = [
    'SlackNotifier',
    'build_pipeline_summary',
    'build_error_alert',
    'build_quota_warning',
]
