"""Fault-injection test package.

Targets deterministic failure paths: circuit-breaker state transitions,
DB query timing failures, FTP partial-file cleanup, and malformed
RouterOS responses. No real routers or network I/O are required.
"""
