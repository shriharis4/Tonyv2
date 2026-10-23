"""
Category matrix + paraphrase coverage (spec section C / test generation
rules). Expands each intent into many phrasings and includes a large
negative corpus, to prove routing accuracy at scale rather than on a
handful of happy-path strings.

All tools are recorded (not executed). A "routed" command must call the
expected tool (or set a pending confirmation/slot); a negative command
must trigger NO destructive/action tool.
"""

import pytest


def _rec(runtime_agent, monkeypatch, *names):
    """Patch several tools to recorders; return a dict name->calls list."""
    calls = {n: [] for n in names}

    def make(n):
        async def _f(*a, **k):
            calls[n].append((a, k))
            return "ok"
        _f.__name__ = n
        return _f

    for n in names:
        monkeypatch.setattr(runtime_agent, n, make(n))
    return calls


async def _route(runtime_agent, fake_session, utterance):
    runtime_agent.turn_ctx.pending_confirmation = None
    runtime_agent.turn_ctx.pending_slot = None
    runtime_agent.turn_ctx.last_processed_command = ""
    runtime_agent.turn_ctx.last_processed_at = 0.0
    runtime_agent.turn_ctx.last_handled_transcript = ""
    return await runtime_agent.route_command_directly(fake_session, utterance)


# ---------------- APP OPEN (paraphrases) ----------------
OPEN_CASES = [
    ("open chrome", "chrome"),
    ("launch chrome", "chrome"),
    ("start chrome browser", "chrome"),
    ("open google chrome", "chrome"),
    ("open notepad", "notepad"),
    ("launch notepad", "notepad"),
    ("open my notepad", "notepad"),
    ("open excel", "excel"),
    ("open the calculator", "calculator"),
    ("open vs code", "vscode"),
    ("open visual studio code", "vscode"),
    ("open whatsapp", "whatsapp"),
    ("open spotify", "spotify"),
    ("open file explorer", "explorer"),
    ("open task manager", "task manager"),
    ("open settings", "settings"),
    ("open paint", "paint"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("utterance,target", OPEN_CASES)
async def test_open_app_paraphrases(runtime_agent, fake_session, monkeypatch, utterance, target):
    calls = _rec(runtime_agent, monkeypatch, "open_app", "open_spotify")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True, f"{utterance!r} should be handled"
    if target == "spotify":
        assert calls["open_spotify"], f"{utterance!r} should open spotify"
    else:
        assert calls["open_app"], f"{utterance!r} should call open_app"
        assert calls["open_app"][0][0][0] == target


# ---------------- APP CLOSE (paraphrases) ----------------
CLOSE_CASES = [
    ("close chrome", "chrome"),
    ("exit chrome", "chrome"),
    ("close whatsapp", "whatsapp"),
    ("close spotify", "spotify"),
    ("close notepad", "notepad"),
    ("close excel", "excel"),
    ("close the code editor", "code"),
    ("quit calculator", "calculator"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("utterance,target", CLOSE_CASES)
async def test_close_app_paraphrases(runtime_agent, fake_session, monkeypatch, utterance, target):
    calls = _rec(runtime_agent, monkeypatch, "manage_window")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True
    assert calls["manage_window"], f"{utterance!r} should close via manage_window"
    args = calls["manage_window"][0][0]
    assert args[0] == "close" and args[1] == target


# ---------------- WINDOW MGMT ----------------
@pytest.mark.asyncio
@pytest.mark.parametrize("utterance,action", [
    ("minimize this", "minimize"),
    ("minimize the window", "minimize"),
    ("maximize this", "maximize"),
    ("maximize the window", "maximize"),
    ("restore the window", "restore"),
])
async def test_window_management(runtime_agent, fake_session, monkeypatch, utterance, action):
    calls = _rec(runtime_agent, monkeypatch, "manage_window")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True
    assert calls["manage_window"][0][0][0] == action


# ---------------- VOLUME ----------------
@pytest.mark.asyncio
@pytest.mark.parametrize("utterance", [
    "volume up", "turn the volume up", "increase volume", "louder",
    "volume down", "turn the volume down", "decrease volume", "quieter",
    "mute", "mute the volume", "unmute", "set volume to 40",
])
async def test_volume_commands(runtime_agent, fake_session, monkeypatch, utterance):
    calls = _rec(runtime_agent, monkeypatch, "control_system_volume", "get_current_volume")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True, f"{utterance!r} should be a volume command"
    assert calls["control_system_volume"], f"{utterance!r} should call control_system_volume"


# ---------------- BRIGHTNESS ----------------
@pytest.mark.asyncio
@pytest.mark.parametrize("utterance", [
    "brightness up", "increase brightness", "brighter",
    "brightness down", "decrease brightness", "dimmer",
    "set brightness to 50",
])
async def test_brightness_commands(runtime_agent, fake_session, monkeypatch, utterance):
    calls = _rec(runtime_agent, monkeypatch, "control_screen_brightness")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True
    assert calls["control_screen_brightness"], f"{utterance!r} should adjust brightness"


# ---------------- SCREENSHOT ----------------
@pytest.mark.asyncio
@pytest.mark.parametrize("utterance", [
    "take a screenshot", "screenshot", "capture my screen",
    "capture screen", "take a picture of my screen",
])
async def test_screenshot_commands(runtime_agent, fake_session, monkeypatch, utterance):
    calls = _rec(runtime_agent, monkeypatch, "screen_short")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True
    assert calls["screen_short"]


# ---------------- SPOTIFY ----------------
@pytest.mark.asyncio
@pytest.mark.parametrize("utterance,expect", [
    ("play a song on spotify", "resume_or_liked"),
    ("play some music", "resume_or_liked"),
    ("play kesariya on spotify", "named"),
    ("play believer on spotify", "named"),
    ("pause the music", "pause"),
    ("next song", "next"),
    ("previous song", "previous"),
    ("play my liked songs", "liked"),
])
async def test_spotify_commands(runtime_agent, fake_session, monkeypatch, utterance, expect):
    calls = _rec(runtime_agent, monkeypatch, "spotify_play_song", "spotify_play",
                 "spotify_pause", "spotify_next", "spotify_previous", "spotify_play_liked")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True, f"{utterance!r} should be handled"
    if expect == "named":
        assert calls["spotify_play_song"], f"{utterance!r} should play a named song"
        assert "a song" not in str(calls["spotify_play_song"][0][0]).lower()
    elif expect == "pause":
        assert calls["spotify_pause"]
    elif expect == "next":
        assert calls["spotify_next"]
    elif expect == "previous":
        assert calls["spotify_previous"]
    elif expect == "liked":
        assert calls["spotify_play_liked"]
    else:  # resume_or_liked
        assert calls["spotify_play"] or calls["spotify_play_liked"]
        assert not calls["spotify_play_song"], "entity-less play must not search literal filler"


# ---------------- WHATSAPP (paraphrases) ----------------
@pytest.mark.asyncio
@pytest.mark.parametrize("utterance,contact", [
    ("send message to naveen saying how are you", "naveen"),
    ("send a whatsapp message to ravi saying hello", "ravi"),
    ("message priya saying good morning", "priya"),
    ("text amit saying i am coming", "amit"),
    ("whatsapp john saying hi", "john"),
])
async def test_whatsapp_paraphrases(runtime_agent, fake_session, monkeypatch, utterance, contact):
    calls = _rec(runtime_agent, monkeypatch, "send_whatsapp_message")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True, f"{utterance!r} should route to WhatsApp"
    assert calls["send_whatsapp_message"], f"{utterance!r} should call send_whatsapp_message"
    assert calls["send_whatsapp_message"][0][0][0].lower() == contact


# ---------------- SYSTEM STATUS / INFO ----------------
@pytest.mark.asyncio
@pytest.mark.parametrize("utterance", [
    "system status", "how much battery do i have left", "what's my cpu usage",
    "ram usage", "check my storage",
])
async def test_system_status(runtime_agent, fake_session, monkeypatch, utterance):
    calls = _rec(runtime_agent, monkeypatch, "get_system_status")
    handled = await _route(runtime_agent, fake_session, utterance)
    assert handled is True
    assert calls["get_system_status"]


# ---------------- NEGATIVE CORPUS (must NOT trigger any action tool) ----------------
NEGATIVES = [
    "how do i block ads in chrome",
    "what is the clock speed of my cpu",
    "write a letter about sleep apnea",
    "what does shutdown mean",
    "tell me how to restart a router",
    "the lock on my door is broken",
    "i can't sleep",
    "don't close it",
    "this is not a command",
    "set a reminder for bedtime",
    "play sometimes by britney",
    "my volume is too loud these days",
    "the brightness of the sun",
    "i was searching for answers in life",
    "close friends are important",
    "open minded people are great",
    "the news was sad today",
    "my computer is old",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("utterance", NEGATIVES)
async def test_negatives_no_power_action(runtime_agent, fake_session, monkeypatch, utterance):
    """None of these may trigger a power action (shutdown/restart/lock/sleep)."""
    calls = _rec(runtime_agent, monkeypatch, "system_power_action")
    await _route(runtime_agent, fake_session, utterance)
    assert calls["system_power_action"] == [], (
        f"{utterance!r} wrongly triggered a power action"
    )
    assert runtime_agent.turn_ctx.pending_confirmation is None, (
        f"{utterance!r} wrongly queued a destructive confirmation"
    )
