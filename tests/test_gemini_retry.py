"""
Tests for Gemini retry-with-backoff and graceful degradation
(core.runtime_agent._generate_reply_with_retry).
"""

import pytest


@pytest.mark.asyncio
async def test_generate_reply_succeeds_first_try(runtime_agent, fake_session):
    runtime_agent._gemini_consecutive_failures = 0
    runtime_agent._gemini_degraded_mode = False

    ok = await runtime_agent._generate_reply_with_retry(fake_session, "hello")
    assert ok is True
    assert runtime_agent._gemini_consecutive_failures == 0


@pytest.mark.asyncio
async def test_generate_reply_retries_once_then_succeeds(runtime_agent, fake_session, monkeypatch):
    calls = {"count": 0}

    async def flaky_generate_reply(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient network blip")
        return None

    monkeypatch.setattr(fake_session, "generate_reply", flaky_generate_reply)
    runtime_agent._gemini_consecutive_failures = 0
    runtime_agent._gemini_degraded_mode = False

    ok = await runtime_agent._generate_reply_with_retry(fake_session, "hello", max_retries=1)
    assert ok is True
    assert calls["count"] == 2  # one failure + one successful retry


@pytest.mark.asyncio
async def test_generate_reply_degrades_gracefully_after_repeated_failures(runtime_agent, fake_session, monkeypatch):
    async def always_fails(**kwargs):
        raise RuntimeError("gemini unreachable")

    monkeypatch.setattr(fake_session, "generate_reply", always_fails)
    monkeypatch.setattr(runtime_agent, "is_network_reachable", lambda *a, **k: True)
    runtime_agent._gemini_consecutive_failures = 0
    runtime_agent._gemini_degraded_mode = False

    # First failure (below threshold) -> generic error message, no degraded notice yet.
    ok1 = await runtime_agent._generate_reply_with_retry(fake_session, "first", max_retries=0)
    assert ok1 is False
    assert runtime_agent._gemini_degraded_mode is False

    # Second consecutive failure hits the threshold -> degraded mode notice.
    ok2 = await runtime_agent._generate_reply_with_retry(fake_session, "second", max_retries=0)
    assert ok2 is False
    assert runtime_agent._gemini_degraded_mode is True

    await __import__("asyncio").sleep(0.05)
    assert any("temporarily limited" in s or "AI engine" in s for s in fake_session.said)


@pytest.mark.asyncio
async def test_generate_reply_never_raises(runtime_agent, fake_session, monkeypatch):
    """The retry wrapper must never let an exception propagate out to the
    caller — handle_user_transcript relies on this for crash isolation."""
    async def always_fails(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(fake_session, "generate_reply", always_fails)
    runtime_agent._gemini_consecutive_failures = 0
    runtime_agent._gemini_degraded_mode = False

    ok = await runtime_agent._generate_reply_with_retry(fake_session, "test", max_retries=0)
    assert ok is False  # returned False, did not raise
