"""Base Collector - Abstract base class and result types for all collectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Generic, TypeVar

T = TypeVar('T')


class ResultStatus(Enum):
    """Status of a collection operation."""
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class Result(Generic[T]):
    """Standard result type for all collectors."""
    status: ResultStatus
    data: Optional[T] = None
    message: str = ""

    @staticmethod
    def success(data: T, message: str = "") -> 'Result[T]':
        """Create a success result."""
        return Result(ResultStatus.SUCCESS, data, message)

    @staticmethod
    def skipped(message: str) -> 'Result[None]':
        """Create a skipped result."""
        return Result(ResultStatus.SKIPPED, None, message)

    @staticmethod
    def error(message: str) -> 'Result[None]':
        """Create an error result."""
        return Result(ResultStatus.ERROR, None, message)

    @property
    def is_success(self) -> bool:
        """Check if result is successful."""
        return self.status == ResultStatus.SUCCESS

    @property
    def is_skipped(self) -> bool:
        """Check if result was skipped."""
        return self.status == ResultStatus.SKIPPED

    @property
    def is_error(self) -> bool:
        """Check if result is an error."""
        return self.status == ResultStatus.ERROR


class BaseCollector(ABC):
    """Abstract base class for all stat collectors.

    Each collector is responsible for:
    1. Checking if data needs updating
    2. Fetching data from external API
    3. Transforming data into domain models
    4. Persisting data via repository
    """

    @abstractmethod
    def collect(self, entity_id: int) -> Result:
        """
        Collect stats for an entity.

        Args:
            entity_id: ID of the entity to collect stats for

        Returns:
            Result containing the collected data or error/skip info
        """
        pass

    @abstractmethod
    def should_update(self, entity_id: int) -> bool:
        """
        Check if entity needs updating.

        Args:
            entity_id: ID of the entity to check

        Returns:
            True if entity needs updating, False otherwise
        """
        pass

    def collect_if_needed(self, entity_id: int) -> Result:
        """
        Collect stats only if entity needs updating.

        Args:
            entity_id: ID of the entity

        Returns:
            Result of collection or skip result
        """
        if not self.should_update(entity_id):
            return Result.skipped(f"Entity {entity_id} is up to date")
        return self.collect(entity_id)
