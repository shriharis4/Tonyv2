"""
Tests for router ambiguity handling and the hardened filler-word stripper
(spec Workstream 2 items 4 and 5).
"""

import pytest


def _patch_tool(monkeypatch, runtime_agent, attr_name, fn_name=None):
    calls = []

    async def _fake(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    _fake.__name__ = fn_name or attr_name
    monkeypatch.setattr(runtime_agent, attr_name, _fake)
    return calls


@pytest.mark.asyncio
async def test_bare_open_asks_for_clarification(runtime_agent, fake_session, monkeypatch):
    """A bare 'open' with no target must ask 'Open what?' rather than
    guessing or firing open_app against nothing."""
    calls = _patch_tool(monkeypatch, runtime_agent, "open_app", "open_app")
    handled = await runtime_agent.route_command_directly(fake_session, "open")
    assert handled is True
    assert calls == []  # no tool fired

    import asyncio
    await asyncio.sleep(0.05)
    assert any("what" in s.lower() for s in fake_session.said)


@pytest.mark.asyncio
async def test_bare_close_asks_for_clarification(runtime_agent, fake_session, monkeypatch):
    calls = _patch_tool(monkeypatch, runtime_agent, "manage_window", "manage_window")
    handled = await runtime_agent.route_command_directly(fake_session, "close")
    assert handled is True
    assert calls == []


@pytest.mark.asyncio
async def test_open_with_target_still_works_after_hardening(runtime_agent, fake_session, monkeypatch):
    """The ambiguity guard and filler changes must not break normal
    'open notepad'."""
    calls = _patch_tool(monkeypatch, runtime_agent, "open_app", "open_app")
    handled = await runtime_agent.route_command_directly(fake_session, "open notepad")
    assert handled is True
    assert calls == [(("notepad",), {})]


@pytest.mark.asyncio
async def test_open_my_notepad_strips_prefix_my(runtime_agent, fake_session, monkeypatch):
    """Leading 'my' is still stripped as filler, so 'open my notepad' opens
    notepad."""
    calls = _patch_tool(monkeypatch, runtime_agent, "open_app", "open_app")
    handled = await runtime_agent.route_command_directly(fake_session, "open my notepad")
    assert handled is True
    assert calls == [(("notepad",), {})]


@pytest.mark.asyncio
async def test_play_alone_is_not_treated_as_ambiguous_verb(runtime_agent, fake_session, monkeypatch):
    """'play' alone is a valid Spotify transport control (resume), so it
    must NOT be swallowed by the ambiguity guard."""
    async def fake_spotify_play():
        return "resumed"
    fake_spotify_play.__name__ = "spotify_play"
    monkeypatch.setattr(runtime_agent, "spotify_play", fake_spotify_play)

    handled = await runtime_agent.route_command_directly(fake_session, "play")
    assert handled is True
    # Should have reached the Spotify block, not the "play what?" clarifier.
    import asyncio
    await asyncio.sleep(0.05)
    assert not any("play what" in s.lower() for s in fake_session.said)
