"""
Slack Block Kit Message Builders

Creates rich, formatted messages for pipeline notifications.
"""

from typing import Any, Dict, List, Optional

from ..types import (
    PipelineResult,
    PipelineStatus,
    StepResult,
    StepStatus,
    format_step_result,
)


def _divider() -> Dict[str, str]:
    """Create a divider block."""
    return {"type": "divider"}


def _header(text: str) -> Dict[str, Any]:
    """Create a header block."""
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": text, "emoji": True},
    }


def _section(text: str) -> Dict[str, Any]:
    """Create a section block with markdown."""
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": text},
    }


def _context(elements: List[str]) -> Dict[str, Any]:
    """Create a context block."""
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": e} for e in elements],
    }


def _build_step_line(step: StepResult) -> str:
    """Build a single step result line."""
    if step.status == StepStatus.SUCCESS:
        emoji = ":white_check_mark:"
        result_str = format_step_result(step.name, step.result) if step.result else "completed"
        return f"{emoji} *{step.name}*: {result_str}"
    elif step.status == StepStatus.FAILED:
        emoji = ":x:"
        error_str = step.error[:50] if step.error else "unknown error"
        return f"{emoji} *{step.name}*: {error_str}"
    else:  # SKIPPED
        return f":fast_forward: *{step.name}*: skipped"


def build_pipeline_summary(result: PipelineResult) -> List[Dict[str, Any]]:
    """
    Build Block Kit blocks for pipeline summary notification.

    Args:
        result: PipelineResult with all step outcomes

    Returns:
        List of Block Kit blocks
    """
    blocks = []

    # Header based on status
    if result.status == PipelineStatus.SUCCESS:
        blocks.append(_header(":white_check_mark: Daily Pipeline Complete"))
    elif result.status == PipelineStatus.PARTIAL:
        blocks.append(_header(":warning: Pipeline Completed with Errors"))
    else:
        blocks.append(_header(":x: Pipeline Failed"))

    blocks.append(_divider())

    # Data Collection section
    data_steps = ["paper_update", "logs", "injuries", "features", "rolling", "props"]
    data_results = [s for s in result.steps if s.name in data_steps]

    if data_results:
        lines = [":bar_chart: *Data Collection*"]
        for step in data_results:
            lines.append(_build_step_line(step))
        blocks.append(_section("\n".join(lines)))

    # Scraping section
    scrape_steps = ["odds_api"]
    scrape_results = [s for s in result.steps if s.name in scrape_steps]

    if scrape_results:
        lines = [":globe_with_meridians: *Props Scraping*"]
        for step in scrape_results:
            lines.append(_build_step_line(step))
        blocks.append(_section("\n".join(lines)))

    # Predictions section
    pred_steps = ["paper_log"]
    pred_results = [s for s in result.steps if s.name in pred_steps]

    if pred_results:
        lines = [":dart: *Predictions*"]
        for step in pred_results:
            lines.append(_build_step_line(step))
        blocks.append(_section("\n".join(lines)))

    # Model check section
    model_steps = ["retrain", "pace"]
    model_results = [s for s in result.steps if s.name in model_steps]

    if model_results:
        lines = [":gear: *Maintenance*"]
        for step in model_results:
            lines.append(_build_step_line(step))
        blocks.append(_section("\n".join(lines)))

    # Model performance section (if available)
    if result.model_performance:
        perf = result.model_performance
        lines = [":chart_with_upwards_trend: *Paper Trading (7d)*"]

        if perf.accuracy_7d is not None:
            lines.append(f"Accuracy: *{perf.accuracy_7d:.1f}%*")
        if perf.roi_7d is not None:
            roi_sign = "+" if perf.roi_7d >= 0 else ""
            lines.append(f"ROI: *{roi_sign}{perf.roi_7d:.1f}%*")
        if perf.pending_predictions > 0:
            lines.append(f"Pending: {perf.pending_predictions} predictions")

        if perf.by_stat:
            stat_parts = [f"{k}: {v:.0f}%" for k, v in perf.by_stat.items()]
            lines.append(f"By stat: {', '.join(stat_parts)}")

        blocks.append(_section("\n".join(lines)))

    blocks.append(_divider())

    # Footer with duration and API quota
    footer_parts = [f":stopwatch: Duration: *{result.duration_str}*"]

    if result.api_health and result.api_health.odds_api_credits_remaining is not None:
        credits = result.api_health.odds_api_credits_remaining
        if credits < 100:
            footer_parts.append(f":warning: Odds API: *{credits}* credits")
        else:
            footer_parts.append(f":credit_card: Odds API: *{credits}* credits")

    blocks.append(_context(footer_parts))

    return blocks


def build_error_alert(
    result: PipelineResult,
    include_traceback: bool = True,
    max_traceback_lines: int = 5,
) -> List[Dict[str, Any]]:
    """
    Build Block Kit blocks for error alert notification.

    Args:
        result: PipelineResult with failure details
        include_traceback: Whether to include stack trace
        max_traceback_lines: Max lines of traceback to show

    Returns:
        List of Block Kit blocks
    """
    blocks = []

    failed_step = result.failed_step
    step_name = failed_step.name if failed_step else "unknown"

    blocks.append(_header(f":x: Pipeline Failed: {step_name} step"))
    blocks.append(_divider())

    # Error details
    if failed_step and failed_step.error:
        error_text = failed_step.error
        # Truncate long errors
        if len(error_text) > 200:
            error_text = error_text[:200] + "..."
        blocks.append(_section(f"*Error:* `{error_text}`"))

    # Completed steps
    completed = result.completed_steps
    if completed:
        lines = ["*Completed steps:*"]
        for step in completed:
            result_str = format_step_result(step.name, step.result) if step.result else ""
            lines.append(f":white_check_mark: {step.name}" + (f" ({result_str})" if result_str else ""))
        lines.append(f":x: {step_name}")
        blocks.append(_section("\n".join(lines)))

    # Stack trace
    if include_traceback and failed_step and failed_step.error_traceback:
        traceback_lines = failed_step.error_traceback.strip().split("\n")
        # Get last N lines
        if len(traceback_lines) > max_traceback_lines:
            traceback_lines = traceback_lines[-max_traceback_lines:]
        traceback_text = "\n".join(traceback_lines)
        blocks.append(_section(f"*Stack trace:*\n```{traceback_text}```"))

    blocks.append(_divider())

    # Footer with timing
    footer_parts = [f":stopwatch: Failed after: *{result.duration_str}*"]
    blocks.append(_context(footer_parts))

    return blocks


def build_quota_warning(
    credits_remaining: int,
    estimated_runs: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Build Block Kit blocks for quota warning notification.

    Args:
        credits_remaining: Current API credits
        estimated_runs: Estimated runs before exhaustion

    Returns:
        List of Block Kit blocks
    """
    blocks = []

    blocks.append(_header(":warning: Odds API Quota Low"))
    blocks.append(_divider())

    lines = [f"*Credits remaining:* {credits_remaining}"]

    if estimated_runs is not None:
        lines.append(f"*Estimated runs before exhaustion:* ~{estimated_runs}")

    lines.append("")
    lines.append("*Consider:*")
    lines.append("- Reducing scrape frequency")
    lines.append("- Adding backup API key")

    blocks.append(_section("\n".join(lines)))

    return blocks


def build_daily_digest(
    accuracy_7d: float,
    roi_7d: float,
    predictions_today: int,
    wins: int,
    losses: int,
    by_stat: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[Dict[str, Any]]:
    """
    Build Block Kit blocks for daily digest notification.

    Args:
        accuracy_7d: 7-day accuracy percentage
        roi_7d: 7-day ROI percentage
        predictions_today: Number of predictions made today
        wins: Wins yesterday
        losses: Losses yesterday
        by_stat: Performance breakdown by stat type

    Returns:
        List of Block Kit blocks
    """
    blocks = []

    blocks.append(_header(":sunrise: Daily Performance Digest"))
    blocks.append(_divider())

    # Yesterday's results
    if wins + losses > 0:
        win_pct = wins / (wins + losses) * 100
        lines = [
            ":calendar: *Yesterday's Results*",
            f"Record: *{wins}-{losses}* ({win_pct:.0f}%)",
        ]
        blocks.append(_section("\n".join(lines)))

    # 7-day performance
    roi_sign = "+" if roi_7d >= 0 else ""
    lines = [
        ":chart_with_upwards_trend: *7-Day Performance*",
        f"Accuracy: *{accuracy_7d:.1f}%*",
        f"ROI: *{roi_sign}{roi_7d:.1f}%*",
    ]
    blocks.append(_section("\n".join(lines)))

    # By stat breakdown
    if by_stat:
        lines = [":bar_chart: *By Stat Type*"]
        for stat, metrics in by_stat.items():
            acc = metrics.get("accuracy", 0)
            count = metrics.get("count", 0)
            lines.append(f"- {stat}: {acc:.0f}% ({count} picks)")
        blocks.append(_section("\n".join(lines)))

    # Today's predictions
    if predictions_today > 0:
        blocks.append(_section(f":dart: *Today's Predictions:* {predictions_today}"))

    return blocks
