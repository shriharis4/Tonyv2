"""
Regression tests for turn-state lifecycle correctness.

Reproduces and guards against the "works for 2-3 commands then gets stuck
in a loop" bug: the LLM-fallback branch of handle_user_transcript used to
leave turn_ctx.state stuck at "LLM_EXECUTION" (it never reset to IDLE the
way the direct-router branch does via _finish_direct_turn), so every
subsequent command hit the "PREEMPTING previous turn" path and the
assistant felt wedged until the 30s safety backstop fired.
"""

import pytest


@pytest.mark.asyncio
async def test_state_returns_to_idle_after_direct_command(runtime_agent, fake_session, monkeypatch):
    async def fake_open_app(name):
        return "opened"
    fake_open_app.__name__ = "open_app"
    monkeypatch.setattr(runtime_agent, "open_app", fake_open_app)

    await runtime_agent.handle_user_transcript(fake_session, "open notepad")
    assert runtime_agent.turn_ctx.state == "IDLE"


@pytest.mark.asyncio
async def test_state_returns_to_idle_after_llm_fallback(runtime_agent, fake_session):
    """The core regression: a command that falls through to the LLM must
    leave state == IDLE afterward, not stuck at LLM_EXECUTION."""
    # "tell me a joke" matches no direct-router intent -> LLM fallback path.
    await runtime_agent.handle_user_transcript(fake_session, "tell me a joke")
    assert runtime_agent.turn_ctx.state == "IDLE", (
        "turn_ctx.state stuck at "
        f"{runtime_agent.turn_ctx.state!r} after LLM fallback - this is the wedge bug"
    )


@pytest.mark.asyncio
async def test_repeated_llm_fallback_commands_do_not_wedge(runtime_agent, fake_session):
    """Simulate the real-world symptom: several LLM-routed commands in a
    row. None should leave the assistant stuck in a non-IDLE state."""
    import time

    for i, cmd in enumerate(["tell me a joke", "what is the meaning of life", "describe quantum physics"]):
        # Space out last_handled_at so duplicate/cooldown suppression
        # doesn't swallow these distinct commands.
        runtime_agent.turn_ctx.last_handled_at = time.perf_counter() - 10
        runtime_agent.turn_ctx.last_processed_at = time.perf_counter() - 10
        await runtime_agent.handle_user_transcript(fake_session, cmd)
        assert runtime_agent.turn_ctx.state == "IDLE", (
            f"Wedged after command #{i + 1} ({cmd!r}): state={runtime_agent.turn_ctx.state!r}"
        )
