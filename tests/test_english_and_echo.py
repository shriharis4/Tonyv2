"""
Regression tests for:
  * English-only display: Tony's reply bubbles and the user's transcript
    bubble must never show Devanagari/non-Latin script.
  * Echo-cancellation wiring in tony.py: the speaker player must be created
    AFTER the AEC microphone on the same MediaDevices, otherwise LiveKit's
    echo canceller has no speaker reference and Tony hears its own voice.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def test_reply_bubble_is_transliterated_to_english(runtime_agent, monkeypatch):
    ra = runtime_agent
    shown = []
    monkeypatch.setitem(ra._gui_callbacks, "stream_start", None)
    monkeypatch.setitem(ra._gui_callbacks, "stream_chunk", None)
    monkeypatch.setitem(ra._gui_callbacks, "stream_end", None)
    monkeypatch.setitem(ra._gui_callbacks, "update_response", lambda t: shown.append(t))
    ra.update_gui_response("मुझे समझ नहीं आया")
    assert shown, "nothing displayed"
    assert not DEVANAGARI.search(shown[0]), f"Devanagari shown: {shown[0]!r}"


def test_user_transcript_bubble_is_english(runtime_agent, monkeypatch):
    ra = runtime_agent
    shown = []
    monkeypatch.setitem(ra._gui_callbacks, "stream_start", None)
    monkeypatch.setitem(ra._gui_callbacks, "stream_replace", None)
    monkeypatch.setitem(ra._gui_callbacks, "stream_end", None)
    monkeypatch.setattr(ra, "update_gui_command", lambda t: shown.append(t))
    ra.update_gui_partial_transcript("व्हाट्सएप खोलो", True)
    assert shown and not DEVANAGARI.search(shown[0]), shown


def test_router_has_no_hardcoded_hindi_replies():
    src = (ROOT / "core" / "runtime_agent.py").read_text(encoding="utf-8")
    bad = [
        line.strip() for line in src.splitlines()
        if "speak_local(" in line and DEVANAGARI.search(line)
    ]
    assert not bad, f"Hindi-script spoken replies remain: {bad}"


def test_tony_creates_speaker_player_after_aec_mic():
    """open_output() must only run via _start_audio_player, and that must be
    awaited AFTER open_input(enable_aec=True) in the startup sequence."""
    src = (ROOT / "tony.py").read_text(encoding="utf-8")
    # Only one open_output() call, inside the helper.
    assert src.count("open_output(") == 1, "extra open_output() call (breaks AEC)"
    helper_start = src.index("async def _start_audio_player")
    helper_end = src.index("def _start_agent_background")
    assert helper_start < src.index("open_output(") < helper_end

    mic_idx = src.index("open_input(input_device=selected_idx, enable_aec=True")
    first_player_start = src.index("await self._start_audio_player()")
    assert mic_idx < first_player_start, (
        "speaker player started before the AEC mic -> echo cancellation disabled"
    )
