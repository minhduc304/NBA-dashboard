"""
Monitoring Types

Data structures for pipeline results and step outcomes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PipelineStatus(Enum):
    """Overall pipeline status."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some steps failed but pipeline continued
    FAILED = "failed"


class StepStatus(Enum):
    """Individual step status."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    name: str
    status: StepStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate step duration in seconds."""
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def duration_str(self) -> str:
        """Human-readable duration."""
        secs = self.duration_seconds
        if secs < 60:
            return f"{secs:.1f}s"
        mins = int(secs // 60)
        remaining_secs = int(secs % 60)
        return f"{mins}m {remaining_secs}s"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ModelPerformance:
    """Model performance metrics from paper trading."""

    accuracy_7d: Optional[float] = None
    roi_7d: Optional[float] = None
    pending_predictions: int = 0
    by_stat: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "accuracy_7d": self.accuracy_7d,
            "roi_7d": self.roi_7d,
            "pending_predictions": self.pending_predictions,
            "by_stat": self.by_stat,
        }


@dataclass
class APIHealth:
    """API health metrics."""

    odds_api_credits_remaining: Optional[int] = None
    odds_api_key_index: int = 0
    odds_api_keys_total: int = 1


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""

    job_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    steps: List[StepResult] = field(default_factory=list)
    model_performance: Optional[ModelPerformance] = None
    api_health: Optional[APIHealth] = None

    @property
    def status(self) -> PipelineStatus:
        """Determine overall pipeline status."""
        if not self.steps:
            return PipelineStatus.FAILED

        failed_steps = [s for s in self.steps if s.status == StepStatus.FAILED]
        if len(failed_steps) == len(self.steps):
            return PipelineStatus.FAILED
        elif failed_steps:
            return PipelineStatus.PARTIAL
        return PipelineStatus.SUCCESS

    @property
    def duration_seconds(self) -> float:
        """Calculate total duration in seconds."""
        if self.ended_at is None:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def duration_str(self) -> str:
        """Human-readable duration."""
        secs = self.duration_seconds
        if secs < 60:
            return f"{secs:.0f}s"
        mins = int(secs // 60)
        remaining_secs = int(secs % 60)
        return f"{mins}m {remaining_secs}s"

    @property
    def completed_steps(self) -> List[StepResult]:
        """Get successfully completed steps."""
        return [s for s in self.steps if s.status == StepStatus.SUCCESS]

    @property
    def failed_steps(self) -> List[StepResult]:
        """Get failed steps."""
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    @property
    def failed_step(self) -> Optional[StepResult]:
        """Get the first failed step (if any)."""
        failed = self.failed_steps
        return failed[0] if failed else None

    def add_step(self, step: StepResult):
        """Add a step result."""
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_name": self.job_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "steps": [s.to_dict() for s in self.steps],
            "model_performance": self.model_performance.to_dict() if self.model_performance else None,
            "api_health": {
                "odds_api_credits_remaining": self.api_health.odds_api_credits_remaining,
            } if self.api_health else None,
        }


def format_step_result(name: str, result: Dict[str, Any]) -> str:
    """Format step result for display based on step type."""
    if name == "paper_update":
        updated = result.get("updated", 0)
        return f"{updated} updated"

    elif name == "logs":
        # Result can be a dict with 'new' or just an int
        if isinstance(result, dict):
            new_games = result.get("new", result.get("games", 0))
        else:
            new_games = result
        return f"{new_games} new games"

    elif name == "injuries":
        if isinstance(result, dict):
            changes = result.get("changes", result.get("count", 0))
        else:
            changes = result
        return f"{changes} status changes"

    elif name == "features":
        home_away = result.get("home_away_updated", 0)
        rest_days = result.get("rest_days_updated", 0)
        opp_rest = result.get("opponent_rest_updated", 0)
        return f"home_away: {home_away}, rest_days: {rest_days}, opponent_rest: {opp_rest}"

    elif name == "rolling":
        if isinstance(result, dict):
            players = result.get("players_updated", result.get("updated", 0))
        else:
            players = result
        return f"{players} players updated"

    elif name == "props":
        if isinstance(result, dict):
            processed = result.get("processed", result.get("count", 0))
        else:
            processed = result
        return f"{processed} props processed"

    elif name == "odds_api":
        events = result.get("events", 0)
        props = result.get("props", 0)
        credits = result.get("credits_remaining")
        credit_str = f", credits: {credits}" if credits is not None else ""
        return f"events: {events}, props: {props}{credit_str}"

    elif name == "paper_log":
        logged = result.get("logged", 0)
        by_stat = result.get("by_stat", {})
        stat_parts = []
        for stat, count in by_stat.items():
            if isinstance(count, int):
                stat_parts.append(f"{stat}: {count}")
        stat_str = ", ".join(stat_parts) if stat_parts else ""
        if stat_str:
            return f"{logged} logged ({stat_str})"
        return f"{logged} logged"

    elif name == "retrain":
        accuracy = result.get("recent_accuracy", "N/A")
        needs_retrain = result.get("needs_retrain", False)
        retrained = result.get("retrained", False)
        status = "retrained" if retrained else ("needs_retrain" if needs_retrain else "ok")
        return f"accuracy: {accuracy}, {status}"

    elif name == "pace":
        if isinstance(result, dict):
            teams = result.get("teams_updated", result.get("updated", 0))
        else:
            teams = result
        return f"{teams} teams updated"

    # Default: just stringify the result
    return str(result) if result else "completed"
