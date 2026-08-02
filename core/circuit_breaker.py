"""Circuit breaker pattern for MikroTik router connections.

Prevents retry storms when a router is repeatedly unreachable by
short-circuiting requests after a configurable failure threshold.

States:
    - CLOSED  : requests flow through; failures are counted.
    - OPEN    : requests fail fast for ``reset_timeout`` seconds.
    - HALF-OPEN: a single trial request is allowed; success closes
                 the circuit, failure re-opens it.
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)

_STATE_OPEN = "OPEN"
_STATE_CLOSED = "CLOSED"
_STATE_HALF_OPEN = "HALF-OPEN"


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit is open and the request is short-circuited."""


class CircuitBreaker:
    """Thread-safe circuit breaker per-router key.

    Args:
        failure_threshold: Consecutive failures before opening the circuit.
        reset_timeout: Seconds to stay open before transitioning to half-open.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: float = 30.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._lock = threading.RLock()
        self._state: dict[str, CircuitState] = {}
        self._failure_count: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}
        self._in_trial: dict[str, bool] = {}

    def _get_state(self, router_key: str) -> CircuitState:
        return self._state.get(router_key, CircuitState.CLOSED)

    def _can_attempt(self, router_key: str) -> bool:
        """Check if a request can proceed (not open, or half-open transition)."""
        with self._lock:
            state = self._get_state(router_key)
            if state == CircuitState.CLOSED:
                return True
            if state == CircuitState.OPEN:
                last_failure = self._last_failure_time.get(router_key, 0.0)
                if time.monotonic() - last_failure >= self._reset_timeout:
                    self._state[router_key] = CircuitState.HALF_OPEN
                    # Claim the single trial slot at the transition so no
                    # concurrent thread can sneak a second trial request in.
                    self._in_trial[router_key] = True
                    logger.info(
                        "Circuit half-open for %s — trial request will be attempted",
                        router_key,
                        extra={"component": "ROUTER"},
                    )
                    return True
                return False
            # HALF_OPEN: only one concurrent trial allowed
            if self._in_trial.get(router_key, False):
                return False  # Trial already in progress
            self._in_trial[router_key] = True
            return True

    def before_request(self, router_key: str) -> None:
        """Called before making a request. Raises if circuit is open."""
        with self._lock:
            if not self._can_attempt(router_key):
                state = self._get_state(router_key)
                logger.warning(
                    "Circuit %s for %s — request short-circuited",
                    state.value,
                    router_key,
                    extra={"component": "ROUTER"},
                )
                raise CircuitBreakerOpenError(
                    f"Circuit open for router {router_key} — skipping request to prevent retry storm"
                )

    def on_success(self, router_key: str) -> None:
        """Called after a successful request; resets failure count and closes circuit."""
        with self._lock:
            prev_state = self._get_state(router_key)
            self._failure_count[router_key] = 0
            self._in_trial.pop(router_key, None)
            if prev_state == CircuitState.HALF_OPEN:
                self._state[router_key] = CircuitState.CLOSED
                logger.info(
                    "Circuit CLOSED for %s after successful trial",
                    router_key,
                    extra={"component": "ROUTER"},
                )
            elif prev_state == CircuitState.OPEN:
                self._state[router_key] = CircuitState.CLOSED

    def on_failure(self, router_key: str) -> None:
        """Called after a failed request; opens circuit if threshold reached."""
        with self._lock:
            state = self._get_state(router_key)
            if state == CircuitState.HALF_OPEN:
                # Trial failed — re-open
                self._failure_count[router_key] = 0
                self._in_trial.pop(router_key, None)
                self._state[router_key] = CircuitState.OPEN
                self._last_failure_time[router_key] = time.monotonic()
                logger.warning(
                    "Circuit re-OPENED for %s after failed trial",
                    router_key,
                    extra={"component": "ROUTER"},
                )
            else:
                self._failure_count[router_key] = self._failure_count.get(router_key, 0) + 1
                count = self._failure_count[router_key]
                if count >= self._failure_threshold and state == CircuitState.CLOSED:
                    self._state[router_key] = CircuitState.OPEN
                    self._last_failure_time[router_key] = time.monotonic()
                    logger.error(
                        "Circuit OPENED for %s after %d consecutive failures "
                        "(reset in %.0fs)",
                        router_key,
                        count,
                        self._reset_timeout,
                        extra={"component": "ROUTER"},
                    )

    def get_state(self, router_key: str) -> CircuitState:
        """Public accessor for monitoring/metrics."""
        with self._lock:
            return self._get_state(router_key)

    def get_failure_count(self, router_key: str) -> int:
        """Public accessor for failure count."""
        with self._lock:
            return self._failure_count.get(router_key, 0)

    def reset(self, router_key: str) -> None:
        """Manually reset a router's circuit (e.g. after configuration change)."""
        with self._lock:
            self._state.pop(router_key, None)
            self._failure_count.pop(router_key, None)
            self._last_failure_time.pop(router_key, None)
            self._in_trial.pop(router_key, None)

    def wrap(self, router_key: str, func: Callable[..., object]) -> Callable[..., object]:
        """Decorator: wraps a callable with circuit-breaker logic."""

        def wrapper(*args: object, **kwargs: object) -> object:
            self.before_request(router_key)
            try:
                result = func(*args, **kwargs)
                self.on_success(router_key)
                return result
            except Exception:  # noqa: BLE001 - catch-all: record circuit failure before re-raising
                self.on_failure(router_key)
                raise

        return wrapper
