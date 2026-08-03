"""Fault-injection tests for the circuit breaker state machine.

These tests drive the CLOSED -> OPEN -> HALF-OPEN transitions with a
patched monotonic clock so the reset-timeout behaviour is deterministic.
"""

from unittest.mock import patch

import pytest

from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState


@pytest.fixture
def breaker():
    return CircuitBreaker(failure_threshold=3, reset_timeout=30.0)


@pytest.fixture
def frozen_clock():
    """Return a mutable list driving core.circuit_breaker.time.monotonic."""
    clock = [1000.0]
    with patch("core.circuit_breaker.time.monotonic", side_effect=lambda: clock[0]):
        yield clock


class TestClosedToOpen:
    def test_below_threshold_stays_closed(self, breaker):  # type: ignore[reportMissingParameterType]
        breaker.on_failure("r1")
        breaker.on_failure("r1")
        assert breaker.get_state("r1") is CircuitState.CLOSED
        assert breaker.get_failure_count("r1") == 2

    def test_threshold_opens_circuit(self, breaker):  # type: ignore[reportMissingParameterType]
        breaker.on_failure("r1")
        breaker.on_failure("r1")
        breaker.on_failure("r1")
        assert breaker.get_state("r1") is CircuitState.OPEN

    def test_open_short_circuits_request(self, breaker):  # type: ignore[reportMissingParameterType]
        for _ in range(3):
            breaker.on_failure("r1")
        with pytest.raises(CircuitBreakerOpenError, match="Circuit open"):
            breaker.before_request("r1")

    def test_success_resets_failure_count(self, breaker):  # type: ignore[reportMissingParameterType]
        breaker.on_failure("r1")
        breaker.on_failure("r1")
        breaker.on_success("r1")
        assert breaker.get_failure_count("r1") == 0
        assert breaker.get_state("r1") is CircuitState.CLOSED


class TestOpenToHalfOpen:
    def test_open_before_reset_timeout_stays_short_circuited(self, breaker, frozen_clock):  # type: ignore[reportMissingParameterType]
        breaker._last_failure_time["r1"] = frozen_clock[0] - 5.0
        breaker._state["r1"] = CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            breaker.before_request("r1")
        assert breaker.get_state("r1") is CircuitState.OPEN

    def test_after_reset_timeout_trial_allowed_and_claims_slot(self, breaker, frozen_clock):  # type: ignore[reportMissingParameterType]
        breaker._last_failure_time["r1"] = frozen_clock[0] - 31.0
        breaker._state["r1"] = CircuitState.OPEN
        breaker.before_request("r1")
        assert breaker.get_state("r1") is CircuitState.HALF_OPEN
        assert breaker._in_trial.get("r1") is True

    def test_second_request_during_trial_is_short_circuited(self, breaker, frozen_clock):  # type: ignore[reportMissingParameterType]
        breaker._last_failure_time["r1"] = frozen_clock[0] - 31.0
        breaker._state["r1"] = CircuitState.OPEN
        breaker.before_request("r1")
        with pytest.raises(CircuitBreakerOpenError):
            breaker.before_request("r1")

    def test_trial_success_closes_circuit(self, breaker, frozen_clock):  # type: ignore[reportMissingParameterType]
        breaker._last_failure_time["r1"] = frozen_clock[0] - 31.0
        breaker._state["r1"] = CircuitState.OPEN
        breaker.before_request("r1")
        breaker.on_success("r1")
        assert breaker.get_state("r1") is CircuitState.CLOSED
        assert breaker.get_failure_count("r1") == 0
        assert breaker._in_trial.get("r1") is None

    def test_trial_failure_reopens_circuit(self, breaker, frozen_clock):  # type: ignore[reportMissingParameterType]
        breaker._last_failure_time["r1"] = frozen_clock[0] - 31.0
        breaker._state["r1"] = CircuitState.OPEN
        breaker.before_request("r1")
        breaker.on_failure("r1")
        assert breaker.get_state("r1") is CircuitState.OPEN
        assert breaker.get_failure_count("r1") == 0
        assert breaker._in_trial.get("r1") is None


class TestReset:
    def test_reset_clears_all_state(self, breaker):  # type: ignore[reportMissingParameterType]
        breaker.on_failure("r1")
        breaker.on_failure("r1")
        breaker.on_failure("r1")
        breaker._in_trial["r1"] = True
        breaker.reset("r1")
        assert breaker.get_state("r1") is CircuitState.CLOSED
        assert breaker.get_failure_count("r1") == 0
        assert breaker._in_trial.get("r1") is None


class TestWrap:
    def test_wrap_success_records_success(self, breaker):  # type: ignore[reportMissingParameterType]
        wrapped = breaker.wrap("r1", lambda: "ok")
        assert wrapped() == "ok"
        assert breaker.get_state("r1") is CircuitState.CLOSED
        assert breaker.get_failure_count("r1") == 0

    def test_wrap_failure_records_failure_and_reraises(self, breaker):  # type: ignore[reportMissingParameterType]
        def boom():
            raise RuntimeError("boom")

        wrapped = breaker.wrap("r1", boom)
        with pytest.raises(RuntimeError, match="boom"):
            wrapped()
        assert breaker.get_failure_count("r1") == 1

    def test_wrap_open_circuit_raises_before_calling(self, breaker):  # type: ignore[reportMissingParameterType]
        for _ in range(3):
            breaker.on_failure("r1")
        wrapped = breaker.wrap("r1", lambda: "never")
        with pytest.raises(CircuitBreakerOpenError):
            wrapped()


class TestHalfOpenLeakedTrial:
    def test_unexpected_exception_does_not_wedge_circuit(self, breaker, frozen_clock):  # type: ignore[reportMissingParameterType]
        """An unreported trial (unexpected exception) must not wedge HALF-OPEN forever."""
        # Open the circuit with 3 consecutive failures
        for _ in range(3):
            breaker.on_failure("r1")
        assert breaker.get_state("r1") is CircuitState.OPEN

        # After the reset window a trial request is admitted (half-open)
        frozen_clock[0] += 31.0
        breaker.before_request("r1")
        assert breaker.get_state("r1") is CircuitState.HALF_OPEN

        # Simulate an unexpected exception: neither on_success nor on_failure
        # is reported back, so the trial slot would otherwise stay wedged.

        # After another reset window the next request must NOT be permanently
        # blocked — the leaked trial must be discarded and the circuit re-opened.
        frozen_clock[0] += 31.0
        with pytest.raises(CircuitBreakerOpenError):
            breaker.before_request("r1")
        assert breaker.get_state("r1") is CircuitState.OPEN

        # And after yet another reset window a fresh trial is allowed again.
        frozen_clock[0] += 31.0
        breaker.before_request("r1")
        assert breaker.get_state("r1") is CircuitState.HALF_OPEN
