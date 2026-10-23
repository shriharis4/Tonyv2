"""
Tests for the MJ-ideology latency fix: on a router MISS, Gemini's native
turn must be allowed to proceed (ONE round-trip) instead of the old
abort + generate_reply second round-trip.
"""

import pytest


class _TrackingSession:
    """Records whether interrupt/clear_user_turn/generate_reply were called."""

    def __init__(self):
        self.interrupt_calls = 0
        self.clear_calls = 0
        self.generate_reply_calls = 0
        self.said = []

    def interrupt(self, force=False):
        self.interrupt_calls += 1

    def clear_user_turn(self):
        self.clear_calls += 1

    async def say(self, text):
        self.said.append(text)

    async def generate_reply(self, **kwargs):
        self.generate_reply_calls += 1
        return None


@pytest.mark.asyncio
async def test_router_miss_does_not_call_generate_reply(runtime_agent, monkeypatch):
    """A command the router can't handle must NOT trigger a second model
    round-trip via generate_reply (that was the big latency cost)."""
    session = _TrackingSession()
    runtime_agent.turn_ctx.state = "IDLE"
    runtime_agent.turn_ctx.last_handled_transcript = ""
    runtime_agent.turn_ctx.last_processed_command = ""
    runtime_agent.turn_ctx.last_processed_at = 0.0
    runtime_agent.turn_ctx.last_handled_at = 0.0

    # "tell me a joke" matches no direct-router intent -> miss.
    await runtime_agent.handle_user_transcript(session, "tell me a joke")

    assert session.generate_reply_calls == 0, (
        "router miss must NOT re-prompt Gemini via generate_reply "
        "(let the native turn respond instead)"
    )
    # And state returns to IDLE (no wedge).
    assert runtime_agent.turn_ctx.state == "IDLE"


@pytest.mark.asyncio
async def test_router_miss_does_not_abort_gemini_upfront(runtime_agent, monkeypatch):
    """On a miss, Gemini's native turn should be left alone (not aborted),
    so it can answer in one round-trip."""
    session = _TrackingSession()
    runtime_agent.turn_ctx.state = "IDLE"
    runtime_agent.turn_ctx.last_handled_transcript = ""
    runtime_agent.turn_ctx.last_processed_command = ""
    runtime_agent.turn_ctx.last_processed_at = 0.0
    runtime_agent.turn_ctx.last_handled_at = 0.0

    await runtime_agent.handle_user_transcript(session, "what is the meaning of life")

    # No forced interrupt of Gemini's native turn on a miss.
    assert session.interrupt_calls == 0, "router miss must not interrupt Gemini's native response"
