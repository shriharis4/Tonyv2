"""
Tests for the Gemini native tool-call wrapper (make_timing_decorator).

Real-run bug (11:08): router and Gemini both ran send_whatsapp_message for
the same command at the same time; the keystrokes interleaved into
"Bbrroohhii". Cause: the old wrapper treated livekit FunctionTool objects as
sync, returned an un-awaited coroutine (logged 0.00s) and let the work run
outside the input lock.
"""

import asyncio
import inspect
import time

import pytest
from livekit.agents import function_tool


def _make_tool(calls, delay=0.0, name="demo_tool"):
    async def demo_tool(contact: str, message: str) -> str:
        """Demo tool."""
        calls.append(("start", contact, message, time.perf_counter()))
        await asyncio.sleep(delay)
        calls.append(("end", contact, message, time.perf_counter()))
        return f"sent {message} to {contact}"
    demo_tool.__name__ = name
    return function_tool(demo_tool)


def test_wrapper_is_function_tool_with_same_schema(runtime_agent):
    ra = runtime_agent
    tool = ra.send_whatsapp_message
    w = ra.make_timing_decorator(tool)
    assert type(w).__name__ == "FunctionTool"
    assert w.info.name == tool.info.name
    assert inspect.signature(w._func) == inspect.signature(tool._func)


def test_every_registered_tool_wraps(runtime_agent):
    import tool_registry
    for t in tool_registry.get_all_tool_functions():
        w = runtime_agent.make_timing_decorator(t)
        assert type(w).__name__ == "FunctionTool", t


@pytest.mark.asyncio
async def test_wrapper_really_awaits_the_tool(runtime_agent):
    ra = runtime_agent
    ra._router_tool_started.clear()
    calls = []
    w = ra.make_timing_decorator(_make_tool(calls, delay=0.05, name="await_tool"))
    res = await w._func(contact="bro", message="hi")
    assert res == "sent hi to bro"
    assert [c[0] for c in calls] == ["start", "end"]


@pytest.mark.asyncio
async def test_gemini_any_tool_blocked_on_router_owned_turn(runtime_agent, fake_session):
    """Router handled the command (aborted Gemini) -> Gemini must not run a
    DIFFERENT tool for the same utterance (observed: close tab + an extra
    perform_computer_action)."""
    ra = runtime_agent
    ra._router_tool_started.clear()
    calls = []
    w = ra.make_timing_decorator(_make_tool(calls, name="other_tool"))
    ra._abort_model_turn(fake_session)  # router claims the current turn
    res = await w._func(contact="x", message="y")
    assert calls == []
    assert "already handled" in res


@pytest.mark.asyncio
async def test_gemini_tool_allowed_on_next_turn(runtime_agent, fake_session):
    ra = runtime_agent
    calls = []
    w = ra.make_timing_decorator(_make_tool(calls, name="next_tool"))
    ra._abort_model_turn(fake_session)
    ra.turn_ctx.next_turn()  # user says something new -> new turn
    await w._func(contact="bro", message="hi")
    assert [c[0] for c in calls] == ["start", "end"]


@pytest.mark.asyncio
async def test_gemini_call_arriving_just_before_new_turn_still_runs(runtime_agent, fake_session):
    """Race: Gemini's tool call for a NEW (router-miss) command arrives a
    moment before our transcript handler opens the new turn. It must run."""
    ra = runtime_agent
    calls = []
    w = ra.make_timing_decorator(_make_tool(calls, name="race_tool"))
    ra._abort_model_turn(fake_session)          # previous command: router

    async def new_turn_soon():
        await asyncio.sleep(0.3)
        ra.turn_ctx.next_turn()                 # new command, router miss

    t = asyncio.create_task(new_turn_soon())
    await w._func(contact="bro", message="hi")
    await t
    assert [c[0] for c in calls] == ["start", "end"]


def test_speech_end_uses_real_livekit_state_name():
    """LiveKit UserState has no 'idle'; speech end is 'listening'. The old
    check never fired, so speech->transcript timing was wrong."""
    import typing
    from pathlib import Path
    import livekit.agents.voice.events as ev
    states = typing.get_args(ev.UserState)
    assert "idle" not in states and "listening" in states
    src = (Path(__file__).resolve().parents[1] / "core" / "runtime_agent.py").read_text(encoding="utf-8")
    assert 'elif ev.new_state in ("listening", "away"):' in src


@pytest.mark.asyncio
async def test_gemini_call_skipped_when_router_already_ran_it(runtime_agent):
    ra = runtime_agent
    calls = []
    tool = _make_tool(calls, name="dup_tool")
    ra._router_tool_started["dup_tool"] = time.perf_counter()
    w = ra.make_timing_decorator(tool)
    res = await w._func(contact="Bro", message="hi")
    assert calls == [], "Gemini duplicate executed the tool again"
    assert "already executed" in res
    ra._router_tool_started.clear()


@pytest.mark.asyncio
async def test_gemini_call_waits_for_router_tool_lock(runtime_agent):
    """A Gemini tool call must never type at the same time as a router
    tool: it has to wait for the shared input lock."""
    ra = runtime_agent
    ra._router_tool_started.clear()
    calls = []
    w = ra.make_timing_decorator(_make_tool(calls, delay=0.0, name="lock_tool"))

    async def router_holds_lock():
        async with ra._input_lock:
            calls.append(("router_start", None, None, time.perf_counter()))
            await asyncio.sleep(0.2)
            calls.append(("router_end", None, None, time.perf_counter()))

    r = asyncio.create_task(router_holds_lock())
    await asyncio.sleep(0.02)
    await w._func(contact="bro", message="hi")
    await r
    order = [c[0] for c in calls]
    assert order == ["router_start", "router_end", "start", "end"], order
