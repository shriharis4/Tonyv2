"""
Owner-reported regression tests (from the re-audited spec at HEAD 4037e68).

These encode the exact phrasings the owner reported failing, plus the
dangerous substring-match false triggers the auditor reproduced by running
the real router. Written to FAIL on the pre-fix code (proving the bugs are
real), then pass after the fixes.

Covers:
- D-02: "block ads in chrome" / "sleep apnea" / "clock speed" must NOT
  lock/sleep the PC.
- D-01/3.1 Spotify: "play a song on spotify" must not search literal "a
  song"; "play stop by spice girls" must not pause.
- D-01/3.1 file search: "search this file" / "search X on my computer"
  must route to local file search, not web.
- D-01 WhatsApp: natural phrasings ("send message to X saying Y", "text X
  ...") must be recognized.
"""

import pytest


def _recorder(runtime_agent, monkeypatch, name):
    calls = []

    async def _fake(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    _fake.__name__ = name
    monkeypatch.setattr(runtime_agent, name, _fake)
    return calls


# ---------- D-02: dangerous power-action false triggers ----------

@pytest.mark.asyncio
async def test_block_ads_does_not_lock_pc(runtime_agent, fake_session, monkeypatch):
    power = _recorder(runtime_agent, monkeypatch, "system_power_action")
    await runtime_agent.route_command_directly(fake_session, "how do i block ads in chrome")
    assert power == [], "'block ads in chrome' must NOT trigger a power action (was locking the PC)"
    assert runtime_agent.turn_ctx.pending_confirmation is None


@pytest.mark.asyncio
async def test_sleep_apnea_does_not_sleep_pc(runtime_agent, fake_session, monkeypatch):
    power = _recorder(runtime_agent, monkeypatch, "system_power_action")
    await runtime_agent.route_command_directly(fake_session, "write a letter about sleep apnea")
    assert power == [], "'sleep apnea' must NOT put the PC to sleep"


@pytest.mark.asyncio
async def test_clock_speed_does_not_lock_pc(runtime_agent, fake_session, monkeypatch):
    power = _recorder(runtime_agent, monkeypatch, "system_power_action")
    await runtime_agent.route_command_directly(fake_session, "what is the clock speed of my cpu")
    assert power == [], "'clock speed' must NOT lock the PC"


@pytest.mark.asyncio
async def test_real_lock_command_still_works(runtime_agent, fake_session, monkeypatch):
    """A genuine 'lock the computer' must still lock."""
    power = _recorder(runtime_agent, monkeypatch, "system_power_action")
    handled = await runtime_agent.route_command_directly(fake_session, "lock the computer")
    assert handled is True
    assert power == [(("lock",), {})]


# ---------- D-01/3.1: Spotify ----------

@pytest.mark.asyncio
async def test_play_a_song_does_not_search_literal_text(runtime_agent, fake_session, monkeypatch):
    song = _recorder(runtime_agent, monkeypatch, "spotify_play_song")
    liked = _recorder(runtime_agent, monkeypatch, "spotify_play_liked")
    resume = _recorder(runtime_agent, monkeypatch, "spotify_play")
    await runtime_agent.route_command_directly(fake_session, "play a song on spotify")
    # Must NOT search for the literal filler words "a song".
    assert song == [] or all("a song" not in str(c).lower() and "some music" not in str(c).lower() for c in song), \
        "'play a song' must not search the literal text 'a song'"
    # Should resume or play liked songs instead.
    assert liked or resume, "entity-less play should resume or play liked songs"


@pytest.mark.asyncio
async def test_play_stop_by_spice_girls_does_not_pause(runtime_agent, fake_session, monkeypatch):
    pause = _recorder(runtime_agent, monkeypatch, "spotify_pause")
    song = _recorder(runtime_agent, monkeypatch, "spotify_play_song")
    await runtime_agent.route_command_directly(fake_session, "play stop by spice girls on spotify")
    assert pause == [], "the word 'stop' inside a song title must not pause playback"


# ---------- D-01/3.1: local file search ----------

@pytest.mark.asyncio
async def test_search_this_file_not_web(runtime_agent, fake_session, monkeypatch):
    web = _recorder(runtime_agent, monkeypatch, "search_web")
    await runtime_agent.route_command_directly(fake_session, "search this file")
    assert web == [], "'search this file' must not go to web search"


@pytest.mark.asyncio
async def test_search_on_my_computer_not_web(runtime_agent, fake_session, monkeypatch):
    web = _recorder(runtime_agent, monkeypatch, "search_web")
    await runtime_agent.route_command_directly(fake_session, "search report.pdf on my computer")
    assert web == [], "'search X on my computer' must not go to web search"


@pytest.mark.asyncio
async def test_real_web_search_still_works(runtime_agent, fake_session, monkeypatch):
    web = _recorder(runtime_agent, monkeypatch, "search_web")
    handled = await runtime_agent.route_command_directly(fake_session, "search the web for the capital of peru")
    assert handled is True
    assert len(web) == 1


# ---------- D-01: WhatsApp natural phrasings ----------

@pytest.mark.asyncio
async def test_whatsapp_send_message_to_x_saying_y(runtime_agent, fake_session, monkeypatch):
    wa = _recorder(runtime_agent, monkeypatch, "send_whatsapp_message")
    handled = await runtime_agent.route_command_directly(
        fake_session, "send message to naveen saying how are you"
    )
    assert handled is True, "'send message to X saying Y' must be recognized"
    assert len(wa) == 1
    args = wa[0][0]
    assert args[0].lower() == "naveen"
    assert "how are you" in args[1].lower()


@pytest.mark.asyncio
async def test_whatsapp_text_x_message(runtime_agent, fake_session, monkeypatch):
    wa = _recorder(runtime_agent, monkeypatch, "send_whatsapp_message")
    handled = await runtime_agent.route_command_directly(
        fake_session, "text naveen saying i am coming"
    )
    assert handled is True
    assert len(wa) == 1
    assert wa[0][0][0].lower() == "naveen"
