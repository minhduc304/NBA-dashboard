"""
Slack Notification Client

Sends Block Kit formatted messages to Slack webhooks.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import requests

from ..config import MonitoringConfig
from ..types import PipelineResult, PipelineStatus
from .blocks import (
    build_daily_digest,
    build_error_alert,
    build_pipeline_summary,
    build_quota_warning,
)

logger = logging.getLogger(__name__)


class SlackNotifier:
    """
    Sends rich notifications to Slack via webhooks.

    Usage:
        config = MonitoringConfig.from_env()
        notifier = SlackNotifier(config)

        # After pipeline completes:
        notifier.notify_pipeline_result(result)

        # On quota warning:
        notifier.notify_quota_warning(credits=73)
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        """
        Initialize Slack notifier.

        Args:
            config: MonitoringConfig with webhook URL
        """
        self.config = config or MonitoringConfig.from_env()
        self._webhook_url = self.config.slack_webhook_url

    @property
    def enabled(self) -> bool:
        """Check if Slack notifications are enabled."""
        return bool(self._webhook_url)

    def _send(self, blocks: List[Dict[str, Any]], text: str = "") -> bool:
        """
        Send Block Kit message to Slack.

        Args:
            blocks: Block Kit blocks
            text: Fallback text for notifications

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.debug("Slack not configured, skipping notification")
            return False

        payload = {
            "blocks": blocks,
            "text": text,  # Fallback for notifications
        }

        try:
            response = requests.post(
                self._webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.debug("Slack notification sent successfully")
            return True

        except requests.RequestException as e:
            logger.error("Failed to send Slack notification: %s", e)
            return False

    def notify_pipeline_result(self, result: PipelineResult) -> bool:
        """
        Send pipeline result notification.

        Sends success summary or error alert based on result status.

        Args:
            result: PipelineResult with step outcomes

        Returns:
            True if sent successfully
        """
        # Check notification settings
        if result.status == PipelineStatus.SUCCESS and not self.config.slack_notify_on_success:
            logger.debug("Success notifications disabled, skipping")
            return False

        if result.status == PipelineStatus.FAILED and not self.config.slack_notify_on_failure:
            logger.debug("Failure notifications disabled, skipping")
            return False

        # Build appropriate message
        if result.status == PipelineStatus.FAILED:
            blocks = build_error_alert(result)
            text = f"Pipeline Failed: {result.failed_step.name if result.failed_step else 'unknown'}"
        else:
            blocks = build_pipeline_summary(result)
            text = f"Pipeline {result.status.value}: {result.duration_str}"

        return self._send(blocks, text)

    def notify_error(
        self,
        result: PipelineResult,
        include_traceback: bool = True,
    ) -> bool:
        """
        Send error alert notification.

        Args:
            result: PipelineResult with failure details
            include_traceback: Whether to include stack trace

        Returns:
            True if sent successfully
        """
        if not self.config.slack_notify_on_failure:
            return False

        blocks = build_error_alert(result, include_traceback=include_traceback)
        failed_step = result.failed_step
        text = f"Pipeline Failed: {failed_step.name if failed_step else 'unknown'}"

        return self._send(blocks, text)

    def notify_quota_warning(
        self,
        credits_remaining: int,
        estimated_runs: Optional[int] = None,
    ) -> bool:
        """
        Send quota warning notification.

        Args:
            credits_remaining: Current API credits
            estimated_runs: Estimated runs before exhaustion

        Returns:
            True if sent successfully
        """
        # Auto-calculate estimated runs if not provided
        if estimated_runs is None and credits_remaining > 0:
            # Rough estimate: ~30 credits per run
            estimated_runs = credits_remaining // 30

        blocks = build_quota_warning(credits_remaining, estimated_runs)
        text = f"Odds API Quota Low: {credits_remaining} credits remaining"

        return self._send(blocks, text)

    def notify_daily_digest(
        self,
        accuracy_7d: float,
        roi_7d: float,
        predictions_today: int = 0,
        wins: int = 0,
        losses: int = 0,
        by_stat: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> bool:
        """
        Send daily performance digest.

        Args:
            accuracy_7d: 7-day accuracy percentage
            roi_7d: 7-day ROI percentage
            predictions_today: Predictions made today
            wins: Wins yesterday
            losses: Losses yesterday
            by_stat: Performance by stat type

        Returns:
            True if sent successfully
        """
        blocks = build_daily_digest(
            accuracy_7d=accuracy_7d,
            roi_7d=roi_7d,
            predictions_today=predictions_today,
            wins=wins,
            losses=losses,
            by_stat=by_stat,
        )
        text = f"Daily Digest: {accuracy_7d:.1f}% accuracy, {roi_7d:+.1f}% ROI (7d)"

        return self._send(blocks, text)

    def send_simple(self, message: str, is_error: bool = False) -> bool:
        """
        Send a simple text message (for backwards compatibility).

        Args:
            message: Message text
            is_error: Whether this is an error message

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False

        emoji = ":x:" if is_error else ":white_check_mark:"
        payload = {"text": f"{emoji} {message}"}

        try:
            response = requests.post(
                self._webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error("Failed to send Slack message: %s", e)
            return False
