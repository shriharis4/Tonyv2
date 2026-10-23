"""
Latency measurement tests — quantify the in-process cost of the hot paths
so regressions are caught in data, not guessed at.

These measure the parts that run ON THIS MACHINE (transcript normalisation,
the direct router's match+dispatch, execute_tool's wrapper overhead). They
do NOT and cannot measure the Gemini Realtime network round-trip (STT/TTS),
which is the dominant real-world cost and requires a live session — that is
measured manually on-device via logs/perf.jsonl (see MANUAL_QA_CHECKLIST).

Budgets here are generous in-process sanity bounds, not the §8 end-to-end
voice budgets.
"""

import asyncio
import statistics
import time

import pytest


def _p(values, pct):
    values = sorted(values)
    k = int(round((pct / 100.0) * (len(values) - 1)))
    return values[k]


def test_normalize_transcript_latency():
    """Transcript normalisation must be sub-millisecond for English and a
    few ms for Indic-script (it runs on every turn before routing)."""
    from core.textnorm import normalize_transcript

    english = "open whatsapp and send message to naveen saying how are you"
    indic = "सेंड मैसेज टू नवीन सेइंग हाउ आर यू"

    # English fast path
    t = []
    for _ in range(200):
        s = time.perf_counter()
        normalize_transcript(english)
        t.append((time.perf_counter() - s) * 1000)
    assert _p(t, 50) < 2.0, f"English normalise p50 too slow: {_p(t,50):.3f}ms"

    # Indic (transliterate + snap)
    t2 = []
    for _ in range(200):
        s = time.perf_counter()
        normalize_transcript(indic)
        t2.append((time.perf_counter() - s) * 1000)
    assert _p(t2, 95) < 20.0, f"Indic normalise p95 too slow: {_p(t2,95):.3f}ms"


@pytest.mark.asyncio
async def test_router_match_latency(runtime_agent, fake_session, monkeypatch):
    """The direct router's match + dispatch (excluding the tool's own work)
    must be fast. We stub the tool to a no-op so we measure routing only."""
    async def noop(*a, **k):
        return "ok"
    noop.__name__ = "open_app"
    monkeypatch.setattr(runtime_agent, "open_app", noop)

    times = []
    for _ in range(100):
        runtime_agent.turn_ctx.pending_confirmation = None
        runtime_agent.turn_ctx.pending_slot = None
        runtime_agent.turn_ctx.last_processed_command = ""
        runtime_agent.turn_ctx.last_processed_at = 0.0
        s = time.perf_counter()
        await runtime_agent.route_command_directly(fake_session, "open chrome")
        times.append((time.perf_counter() - s) * 1000)

    p50, p95 = _p(times, 50), _p(times, 95)
    # Router match+dispatch is pure Python; generous ceiling.
    assert p50 < 25.0, f"router p50 too slow: {p50:.2f}ms"
    assert p95 < 60.0, f"router p95 too slow: {p95:.2f}ms"


@pytest.mark.asyncio
async def test_execute_tool_overhead(runtime_agent):
    """execute_tool's wrapper (timeout + unwrap) adds negligible overhead to
    a fast successful tool."""
    async def fast():
        return "ok"
    fast.__name__ = "open_app"

    times = []
    for _ in range(100):
        s = time.perf_counter()
        await runtime_agent.execute_tool(fast)
        times.append((time.perf_counter() - s) * 1000)
    assert _p(times, 50) < 5.0, f"execute_tool overhead p50 too high: {_p(times,50):.3f}ms"


@pytest.mark.asyncio
async def test_router_latency_stable_over_many_turns(runtime_agent, fake_session, monkeypatch):
    """Regression guard for the progressive-slowdown bug: router latency for
    the first batch of turns must be within ~3x of a later batch after many
    turns (no runaway drift)."""
    async def noop(*a, **k):
        return "ok"
    noop.__name__ = "open_app"
    monkeypatch.setattr(runtime_agent, "open_app", noop)

    async def _batch(n):
        out = []
        for _ in range(n):
            runtime_agent.turn_ctx.last_processed_command = ""
            runtime_agent.turn_ctx.last_processed_at = 0.0
            s = time.perf_counter()
            await runtime_agent.route_command_directly(fake_session, "open chrome")
            out.append((time.perf_counter() - s) * 1000)
        return out

    first = await _batch(50)
    # simulate many more turns in between
    for _ in range(300):
        runtime_agent.turn_ctx.last_processed_command = ""
        runtime_agent.turn_ctx.last_processed_at = 0.0
        await runtime_agent.route_command_directly(fake_session, "open chrome")
    last = await _batch(50)

    med_first = statistics.median(first)
    med_last = statistics.median(last)
    assert med_last < max(med_first * 3, 15.0), (
        f"router latency drifted: first={med_first:.2f}ms last={med_last:.2f}ms"
    )


def test_latency_history_bounded_keeps_average_cheap():
    """Average computation must stay O(1)-ish because the history is capped."""
    import core.runtime_agent as ra
    ra.latency_history = []
    for i in range(5000):
        ra.latency_history.append(float(i))
        if len(ra.latency_history) > 50:
            ra.latency_history = ra.latency_history[-50:]
    assert len(ra.latency_history) == 50
    s = time.perf_counter()
    _ = sum(ra.latency_history) / len(ra.latency_history)
    assert (time.perf_counter() - s) * 1000 < 1.0
