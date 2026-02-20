"""Tests for retry logic (retry.py)."""

import pytest
from unittest.mock import MagicMock, patch

from src.api.retry import RetryStrategy, ThrottleDetector, with_retry


# RetryStrategy._calculate_delay

class TestCalculateDelay:
    def test_exponential_backoff_attempt_0(self):
        strategy = RetryStrategy(base_delay=1.0, exponential_backoff=True)
        assert strategy._calculate_delay(0) == 1.0  # 1.0 * 2^0

    def test_exponential_backoff_attempt_1(self):
        strategy = RetryStrategy(base_delay=1.0, exponential_backoff=True)
        assert strategy._calculate_delay(1) == 2.0  # 1.0 * 2^1

    def test_exponential_backoff_attempt_2(self):
        strategy = RetryStrategy(base_delay=1.0, exponential_backoff=True)
        assert strategy._calculate_delay(2) == 4.0  # 1.0 * 2^2

    def test_exponential_backoff_custom_base(self):
        strategy = RetryStrategy(base_delay=0.5, exponential_backoff=True)
        assert strategy._calculate_delay(3) == 4.0  # 0.5 * 2^3

    def test_linear_delay_is_constant(self):
        strategy = RetryStrategy(base_delay=2.0, exponential_backoff=False)
        assert strategy._calculate_delay(0) == 2.0
        assert strategy._calculate_delay(1) == 2.0
        assert strategy._calculate_delay(5) == 2.0


# RetryStrategy.execute

class TestExecute:
    def test_success_on_first_try(self):
        strategy = RetryStrategy(max_retries=3)
        func = MagicMock(return_value="ok")
        result = strategy.execute(func)
        assert result == "ok"
        assert func.call_count == 1

    @patch("src.api.retry.time.sleep")
    def test_success_after_retries(self, mock_sleep):
        strategy = RetryStrategy(max_retries=3, base_delay=0.1)
        func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])
        result = strategy.execute(func)
        assert result == "ok"
        assert func.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("src.api.retry.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        strategy = RetryStrategy(max_retries=2, base_delay=0.1)
        func = MagicMock(side_effect=ValueError("always fails"))
        with pytest.raises(ValueError, match="always fails"):
            strategy.execute(func)
        assert func.call_count == 2

    @patch("src.api.retry.time.sleep")
    def test_only_retries_specified_exceptions(self, mock_sleep):
        strategy = RetryStrategy(
            max_retries=3,
            base_delay=0.1,
            retryable_exceptions=[ConnectionError],
        )
        func = MagicMock(side_effect=ValueError("not retryable"))
        with pytest.raises(ValueError):
            strategy.execute(func)
        assert func.call_count == 1  # No retry for unhandled exception type

    @patch("src.api.retry.time.sleep")
    def test_retries_specified_exception(self, mock_sleep):
        strategy = RetryStrategy(
            max_retries=3,
            base_delay=0.1,
            retryable_exceptions=[ConnectionError],
        )
        func = MagicMock(side_effect=[ConnectionError(), ConnectionError(), "ok"])
        result = strategy.execute(func)
        assert result == "ok"
        assert func.call_count == 3

    @patch("src.api.retry.time.sleep")
    def test_on_retry_callback(self, mock_sleep):
        strategy = RetryStrategy(max_retries=3, base_delay=0.1)
        func = MagicMock(side_effect=[ValueError("e1"), ValueError("e2"), "ok"])
        callback = MagicMock()
        strategy.execute(func, on_retry=callback)
        assert callback.call_count == 2
        # First callback: attempt=1, second: attempt=2
        assert callback.call_args_list[0][0][0] == 1
        assert callback.call_args_list[1][0][0] == 2

    @patch("src.api.retry.time.sleep")
    def test_exponential_delays(self, mock_sleep):
        strategy = RetryStrategy(max_retries=4, base_delay=1.0, exponential_backoff=True)
        func = MagicMock(
            side_effect=[ValueError(), ValueError(), ValueError(), "ok"]
        )
        strategy.execute(func)
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    @patch("src.api.retry.time.sleep")
    def test_linear_delays(self, mock_sleep):
        strategy = RetryStrategy(max_retries=4, base_delay=1.5, exponential_backoff=False)
        func = MagicMock(
            side_effect=[ValueError(), ValueError(), ValueError(), "ok"]
        )
        strategy.execute(func)
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == [1.5, 1.5, 1.5]

    def test_max_retries_one_no_retry(self):
        strategy = RetryStrategy(max_retries=1)
        func = MagicMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            strategy.execute(func)
        assert func.call_count == 1


# with_retry decorator

class TestWithRetryDecorator:
    @patch("src.api.retry.time.sleep")
    def test_decorator_success(self, mock_sleep):
        @with_retry(max_retries=2, base_delay=0.1)
        def my_func(x):
            return x * 2

        assert my_func(5) == 10

    @patch("src.api.retry.time.sleep")
    def test_decorator_retries_on_failure(self, mock_sleep):
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.1)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("flaky")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    @patch("src.api.retry.time.sleep")
    def test_decorator_raises_after_exhaustion(self, mock_sleep):
        @with_retry(max_retries=2, base_delay=0.1)
        def always_fails():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            always_fails()

    @patch("src.api.retry.time.sleep")
    def test_decorator_preserves_function_name(self, mock_sleep):
        @with_retry(max_retries=2)
        def my_named_function():
            pass

        assert my_named_function.__name__ == "my_named_function"

    @patch("src.api.retry.time.sleep")
    def test_decorator_with_kwargs(self, mock_sleep):
        @with_retry(max_retries=2, base_delay=0.1)
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        assert greet("World", greeting="Hi") == "Hi, World!"


# ThrottleDetector

class TestThrottleDetector:
    def test_no_cooldown_below_threshold(self):
        throttle = ThrottleDetector(threshold=3)
        assert throttle.record_failure() is None
        assert throttle.record_failure() is None

    def test_cooldown_at_threshold(self):
        throttle = ThrottleDetector(threshold=3, cooldown=60.0)
        throttle.record_failure()
        throttle.record_failure()
        wait = throttle.record_failure()
        assert wait == 60.0

    def test_success_resets_counter(self):
        throttle = ThrottleDetector(threshold=3, cooldown=60.0)
        throttle.record_failure()
        throttle.record_failure()
        throttle.record_success()
        # Should need 3 more failures after reset
        assert throttle.record_failure() is None
        assert throttle.record_failure() is None
        wait = throttle.record_failure()
        assert wait == 60.0

    def test_escalation(self):
        throttle = ThrottleDetector(threshold=2, cooldown=30.0, max_cooldown=300.0)
        # First trigger: 30s
        throttle.record_failure()
        assert throttle.record_failure() == 30.0
        # Second trigger: 60s
        throttle.record_failure()
        assert throttle.record_failure() == 60.0
        # Third trigger: 90s
        throttle.record_failure()
        assert throttle.record_failure() == 90.0

    def test_max_cooldown_cap(self):
        throttle = ThrottleDetector(threshold=1, cooldown=100.0, max_cooldown=250.0)
        assert throttle.record_failure() == 100.0
        assert throttle.record_failure() == 200.0
        assert throttle.record_failure() == 250.0  # Capped
        assert throttle.record_failure() == 250.0  # Stays capped

    def test_success_resets_escalation(self):
        throttle = ThrottleDetector(threshold=1, cooldown=60.0)
        assert throttle.record_failure() == 60.0   # escalation 1
        assert throttle.record_failure() == 120.0  # escalation 2
        throttle.record_success()
        assert throttle.record_failure() == 60.0   # reset to escalation 1
