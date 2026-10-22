"""
Tests for the direct router (core.runtime_agent.route_command_directly).

Covers: app launch/close word-boundary correctness (the spec's cited
"code" substring bug), destructive-action confirmation gating for
system_power_action, and basic intent coverage. All underlying tool
functions are monkeypatched so no real desktop automation occurs.
"""

import pytest


def _patch_tool(monkeypatch, runtime_agent, attr_name, fn_name=None, return_value="ok"):
    """Replace a tool reference on the runtime_agent module with an async
    mock that records calls and returns a canned value."""
    calls = []

    async def _fake(*args, **kwargs):
        calls.append((args, kwargs))
        return return_value

    _fake.__name__ = fn_name or attr_name
    monkeypatch.setattr(runtime_agent, attr_name, _fake)
    return calls


@pytest.mark.asyncio
async def test_close_code_editor_word_boundary_bug_fixed(runtime_agent, fake_session, monkeypatch):
    """Spec-cited bug: 'close the code editor' must resolve to the 'code'
    target via word boundary matching, not a loose substring match that
    could also fire for unrelated phrases containing 'code'."""
    calls = _patch_tool(monkeypatch, runtime_agent, "manage_window", "manage_window")
    handled = await runtime_agent.route_command_directly(fake_session, "close the code editor")
    assert handled is True
    assert calls == [(("close", "code"), {})]


@pytest.mark.asyncio
async def test_write_code_does_not_open_vscode(runtime_agent, fake_session, monkeypatch):
    """Negative test for the same bug: phrasing like 'write code for X' must
    NOT be interpreted as a request to open VS Code."""
    _patch_tool(monkeypatch, runtime_agent, "open_app", "open_app")
    handled = await runtime_agent.route_command_directly(fake_session, "write code for a calculator")
    assert handled is False


@pytest.mark.asyncio
async def test_open_vscode_still_works(runtime_agent, fake_session, monkeypatch):
    calls = _patch_tool(monkeypatch, runtime_agent, "open_app", "open_app")
    handled = await runtime_agent.route_command_directly(fake_session, "open vs code")
    assert handled is True
    assert calls == [(("vscode",), {})]


@pytest.mark.asyncio
async def test_close_chrome(runtime_agent, fake_session, monkeypatch):
    calls = _patch_tool(monkeypatch, runtime_agent, "manage_window", "manage_window")
    handled = await runtime_agent.route_command_directly(fake_session, "close chrome")
    assert handled is True
    assert calls == [(("close", "chrome"), {})]


@pytest.mark.asyncio
async def test_open_notepad(runtime_agent, fake_session, monkeypatch):
    calls = _patch_tool(monkeypatch, runtime_agent, "open_app", "open_app")
    handled = await runtime_agent.route_command_directly(fake_session, "open notepad")
    assert handled is True
    assert calls == [(("notepad",), {})]


@pytest.mark.asyncio
async def test_shutdown_requires_confirmation_not_executed_immediately(runtime_agent, fake_session, monkeypatch):
    """Acceptance criterion: no destructive action executes without
    explicit confirmation."""
    calls = _patch_tool(monkeypatch, runtime_agent, "system_power_action", "system_power_action")
    handled = await runtime_agent.route_command_directly(fake_session, "shut down the computer")
    assert handled is True
    assert calls == []  # must NOT have executed yet
    assert runtime_agent.turn_ctx.pending_confirmation is not None
    assert runtime_agent.turn_ctx.pending_confirmation["action"] == "shutdown"


@pytest.mark.asyncio
async def test_shutdown_cancelled_on_no(runtime_agent, fake_session, monkeypatch):
    calls = _patch_tool(monkeypatch, runtime_agent, "system_power_action", "system_power_action")
    await runtime_agent.route_command_directly(fake_session, "shut down the computer")
    handled = await runtime_agent.route_command_directly(fake_session, "no")
    assert handled is True
    assert calls == []
    assert runtime_agent.turn_ctx.pending_confirmation is None


@pytest.mark.asyncio
async def test_shutdown_executes_on_explicit_yes(runtime_agent, fake_session, monkeypatch):
    calls = _patch_tool(monkeypatch, runtime_agent, "system_power_action", "system_power_action")
    await runtime_agent.route_command_directly(fake_session, "shut down the computer")
    handled = await runtime_agent.route_command_directly(fake_session, "yes")
    assert handled is True
    assert len(calls) == 1
    assert calls[0] == (("shutdown",), {})


@pytest.mark.asyncio
async def test_restart_requires_confirmation(runtime_agent, fake_session, monkeypatch):
    calls = _patch_tool(monkeypatch, runtime_agent, "system_power_action", "system_power_action")
    handled = await runtime_agent.route_command_directly(fake_session, "restart the computer")
    assert handled is True
    assert calls == []
    assert runtime_agent.turn_ctx.pending_confirmation["action"] == "restart"


@pytest.mark.asyncio
async def test_lock_executes_immediately_no_confirmation_needed(runtime_agent, fake_session, monkeypatch):
    """Lock/sleep are reversible, non-destructive — they should NOT be
    gated behind a confirmation step."""
    calls = _patch_tool(monkeypatch, runtime_agent, "system_power_action", "system_power_action")
    handled = await runtime_agent.route_command_directly(fake_session, "lock the computer")
    assert handled is True
    assert len(calls) == 1
    assert calls[0] == (("lock",), {})
    assert runtime_agent.turn_ctx.pending_confirmation is None


@pytest.mark.asyncio
async def test_ambiguous_open_it_falls_through(runtime_agent, fake_session, monkeypatch):
    """'Open it' with no target should not match any specific app and
    should fall through to the LLM (handled == False) rather than guessing."""
    calls = _patch_tool(monkeypatch, runtime_agent, "open_app", "open_app")
    handled = await runtime_agent.route_command_directly(fake_session, "open it")
    assert handled is False
    assert calls == []


@pytest.mark.asyncio
async def test_unknown_command_falls_through_to_llm(runtime_agent, fake_session):
    """Unsupported/unrecognized requests should return False (falls
    through to Gemini) rather than crashing."""
    handled = await runtime_agent.route_command_directly(fake_session, "defragment my hard drive")
    assert handled is False


@pytest.mark.asyncio
async def test_screenshot_intent(runtime_agent, fake_session, monkeypatch):
    calls = _patch_tool(monkeypatch, runtime_agent, "screen_short", "screen_short")
    handled = await runtime_agent.route_command_directly(fake_session, "take a screenshot")
    assert handled is True
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_time_query_no_tool_needed(runtime_agent, fake_session):
    handled = await runtime_agent.route_command_directly(fake_session, "what time is it")
    assert handled is True
    assert len(fake_session.said) == 0  # speak_local_background runs as a task; say() recorded async

    await __import__("asyncio").sleep(0.05)  # let the background speak task run
    assert any("It's" in s for s in fake_session.said)


@pytest.mark.asyncio
async def test_router_never_raises_on_tool_exception(runtime_agent, fake_session, monkeypatch):
    """Crash isolation: a tool raising an exception must not propagate out
    of route_command_directly — it should degrade to a graceful message."""
    async def boom(*args, **kwargs):
        raise RuntimeError("simulated crash")
    boom.__name__ = "open_app"
    monkeypatch.setattr(runtime_agent, "open_app", boom)

    # execute_tool already isolates exceptions, so this should complete
    # normally (handled True) without raising.
    handled = await runtime_agent.route_command_directly(fake_session, "open notepad")
    assert handled is True
