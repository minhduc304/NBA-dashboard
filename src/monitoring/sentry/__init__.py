"""
Sentry Error Tracking Module

Provides exception capture with rich context for debugging.
"""

from .setup import (
    init_sentry,
    set_pipeline_context,
    add_breadcrumb,
    capture_exception,
    capture_message,
)

__all__ = [
    'init_sentry',
    'set_pipeline_context',
    'add_breadcrumb',
    'capture_exception',
    'capture_message',
]
