"""
Regression fixtures for commit 4037e68 and its follow-up fixes
(spec section B2, cases H-01..H-18). These encode the auditor's defects.

Cases that are fixable and verifiable without live Windows hardware are
asserted here. Cases that require live hardware / audio / Office / a real
browser are documented in tests/MANUAL_QA_CHECKLIST.md and skipped with a
reason, rather than faked.
"""

import glob
import os
import re

import pytest


def _recorder(runtime_agent, monkeypatch, name):
    calls = []

    async def _fake(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    _fake.__name__ = name
    monkeypatch.setattr(runtime_agent, name, _fake)
    return calls


# ---------- H-01: WhatsApp natural phrasings route correctly ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("utterance,contact", [
    ("send message to naveen saying how are you", "naveen"),
    ("send a whatsapp message to naveen saying hi", "naveen"),
    ("text naveen saying i am coming", "naveen"),
])
async def test_h01_whatsapp_natural_phrasings(runtime_agent, fake_session, monkeypatch, utterance, contact):
    wa = _recorder(runtime_agent, monkeypatch, "send_whatsapp_message")
    handled = await runtime_agent.route_command_directly(fake_session, utterance)
    assert handled is True, f"{utterance!r} must be handled, not fall through unhandled"
    assert len(wa) == 1 and wa[0][0][0].lower() == contact


@pytest.mark.asyncio
async def test_h01_whatsapp_slot_fill_asks_once(runtime_agent, fake_session, monkeypatch):
    wa = _recorder(runtime_agent, monkeypatch, "send_whatsapp_message")
    # contact given, message missing -> should ask, store pending slot, NOT send yet.
    # (Uses a phrasing without " and " so it isn't pre-split by the multi-step
    # splitter, which is a separate known gap tracked as D-10.)
    handled = await runtime_agent.route_command_directly(fake_session, "send message to naveen")
    assert handled is True
    assert wa == []
    assert runtime_agent.turn_ctx.pending_slot is not None
    # next utterance is the message body -> now it sends
    handled2 = await runtime_agent.route_command_directly(fake_session, "how are you")
    assert handled2 is True
    assert len(wa) == 1
    assert "how are you" in wa[0][0][1].lower()


# ---------- H-02: Spotify entity handling ----------

@pytest.mark.asyncio
async def test_h02_play_a_song_no_literal_search(runtime_agent, fake_session, monkeypatch):
    song = _recorder(runtime_agent, monkeypatch, "spotify_play_song")
    resume = _recorder(runtime_agent, monkeypatch, "spotify_play")
    liked = _recorder(runtime_agent, monkeypatch, "spotify_play_liked")
    await runtime_agent.route_command_directly(fake_session, "play a song on spotify")
    assert song == [], "must not search literal 'a song'"
    assert resume or liked


@pytest.mark.asyncio
async def test_h02_play_named_song(runtime_agent, fake_session, monkeypatch):
    song = _recorder(runtime_agent, monkeypatch, "spotify_play_song")
    await runtime_agent.route_command_directly(fake_session, "play the song believer on spotify")
    assert len(song) == 1
    q = song[0][0][0].lower()
    assert "believer" in q and q != "a song"


# ---------- H-03: local vs web search ----------

@pytest.mark.asyncio
async def test_h03_local_file_search(runtime_agent, fake_session, monkeypatch):
    web = _recorder(runtime_agent, monkeypatch, "search_web")
    local = _recorder(runtime_agent, monkeypatch, "universal_file_opener")
    await runtime_agent.route_command_directly(fake_session, "search report.pdf on my computer")
    assert web == [], "local file search must not hit web"
    assert len(local) == 1


@pytest.mark.asyncio
async def test_h03_web_search_still_web(runtime_agent, fake_session, monkeypatch):
    web = _recorder(runtime_agent, monkeypatch, "search_web")
    handled = await runtime_agent.route_command_directly(fake_session, "search for nearest pizza")
    assert handled is True and len(web) == 1


# ---------- H-04: negative corpus (no false power/time/date triggers) ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("utterance", [
    "how do i block ads in chrome",
    "what is the clock speed of my cpu",
    "write a letter about sleep apnea",
    "what does shutdown mean",
    "tell me how to restart a router",
    "the lock on my door is broken",
])
async def test_h04_no_false_power(runtime_agent, fake_session, monkeypatch, utterance):
    power = _recorder(runtime_agent, monkeypatch, "system_power_action")
    await runtime_agent.route_command_directly(fake_session, utterance)
    assert power == [], f"{utterance!r} must not trigger any power action"
    assert runtime_agent.turn_ctx.pending_confirmation is None


@pytest.mark.asyncio
@pytest.mark.parametrize("utterance", [
    "lock the computer", "lock my pc", "put the pc to sleep",
])
async def test_h04_anchored_power_still_works(runtime_agent, fake_session, monkeypatch, utterance):
    power = _recorder(runtime_agent, monkeypatch, "system_power_action")
    handled = await runtime_agent.route_command_directly(fake_session, utterance)
    assert handled is True
    assert len(power) == 1


# ---------- H-05: registry consistency ----------

def test_h05_registry_has_name_lookup():
    from tool_registry import get_tool_by_name, get_all_tool_functions
    # Core action tools must be resolvable by name for execute_multi_task.
    for name in ("open_app", "send_whatsapp_message", "spotify_play_song", "control_system_volume"):
        assert get_tool_by_name(name) is not None, f"{name} not resolvable from registry"


def test_h05_llm_list_includes_critical_action_tools():
    """The LLM tool list must include the core action tools so natural
    phrasings reaching Gemini can execute (not just the router)."""
    import core.runtime_agent as ra
    # The curated list is built in UltimateAdvancedTony.__init__; assert the
    # module imported the critical tools (they're referenced there).
    src = open(os.path.join(os.path.dirname(ra.__file__), "runtime_agent.py"), encoding="utf-8").read()
    # Find the tools = [ ... ] block in UltimateAdvancedTony.
    block = src[src.index("DYNAMIC TOOL GROUPING"):]
    block = block[:block.index("wrapped_tools")]
    for name in ("send_whatsapp_message", "spotify_play_song", "open_app",
                 "control_system_volume", "universal_file_opener"):
        assert name in block, f"{name} missing from the LLM tool list (N-01)"


# ---------- H-10: no blocking time.sleep in core/ (static) ----------

def test_h10_no_blocking_sleep_in_core():
    """core/ must not use bare time.sleep in async paths. (Tools/ still has
    legacy blocking sleeps — tracked as a known gap in the report; this
    guards the core router/agent at least.)"""
    core_dir = os.path.join(os.path.dirname(__import__("core.runtime_agent", fromlist=["x"]).__file__))
    offenders = []
    for path in glob.glob(os.path.join(core_dir, "*.py")):
        text = open(path, encoding="utf-8").read()
        # bare time.sleep not prefixed by asyncio.
        if re.search(r"(?<!asyncio\.)\btime\.sleep\(", text):
            offenders.append(os.path.basename(path))
    assert offenders == [], f"blocking time.sleep found in core/: {offenders}"


# ---------- H-13: no shell=True in computer_use launch ----------

def test_h13_no_shell_true_in_computer_use():
    import Tools.computer_use as cu
    text = open(cu.__file__, encoding="utf-8").read()
    assert "shell=True" not in text, "perform_computer_action must not use shell=True (injection risk)"


# ---------- H-17: execute_multi_task resolves tools via registry ----------

@pytest.mark.asyncio
async def test_h17_multi_task_resolves_real_tool(monkeypatch):
    import Tools.multi_task as mt
    import tool_registry

    called = {}

    async def fake_open_app(app_name):
        called["app"] = app_name
        return "opened"
    fake_open_app.__name__ = "open_app"

    # Make the registry resolve open_app to our fake.
    monkeypatch.setattr(tool_registry, "get_tool_by_name",
                        lambda name: fake_open_app if name == "open_app" else None)

    result = await mt.execute_multi_task._func(
        [{"tool_name": "open_app", "params": {"app_name": "notepad"}}]
    )
    assert "not found" not in result.lower(), f"multi_task could not resolve open_app: {result}"
    assert called.get("app") == "notepad"
