"""Concurrency stress test package.

Deterministic, thread-based stress tests: circuit-breaker trial-slot
exclusivity, connection-pool ceiling enforcement, and retry-storm
short-circuiting. Every test completes without relying on wall-clock
timing or real routers.
"""
