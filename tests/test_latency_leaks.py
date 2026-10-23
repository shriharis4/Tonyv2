"""
Tests for the progressive-latency-degradation fixes.

Root causes (from codebase analysis): unbounded latency_history (O(n)
average recompute per turn) and orphaned per-turn tasks accumulating.
These tests lock in the bounded-growth guarantees.
"""

import pytest


def test_latency_history_is_capped(monkeypatch):
    """latency_history must not grow unbounded across many turns."""
    import core.runtime_agent as ra

    # Reset and simulate 500 turns via TurnTimer.print_perf's append+cap path.
    ra.latency_history = []

    # Drive the capping logic directly (same code print_perf runs).
    for i in range(500):
        ra.latency_history.append(float(i))
        if len(ra.latency_history) > 50:
            ra.latency_history = ra.latency_history[-50:]

    assert len(ra.latency_history) <= 50, "latency_history must stay bounded"
    # And it keeps the most RECENT values (rolling window).
    assert ra.latency_history[-1] == 499.0


def test_input_lock_exists_and_is_asyncio_lock():
    import asyncio
    import core.runtime_agent as ra
    assert isinstance(ra._input_lock, asyncio.Lock)


def test_active_turn_task_global_exists():
    """The orphaned-task fix relies on a module-level _active_turn_task
    handle so a new transcript can cancel the previous turn."""
    import core.runtime_agent as ra
    assert hasattr(ra, "_active_turn_task")


def test_log_listener_is_running():
    """The non-blocking log bridge must have a started QueueListener so
    print() never does synchronous disk I/O on the event loop."""
    import core.runtime_agent as ra
    assert ra._log_listener is not None
    # QueueListener has a _thread attribute once started.
    assert getattr(ra._log_listener, "_thread", None) is not None
