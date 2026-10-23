"""
Tests for transcript normalisation (core/textnorm.py).

The owner's requirement: whatever language is spoken, the transcript must
be written in English/Latin script (never Devanagari/Telugu/Kannada). These
tests assert the normaliser (1) never leaves non-Latin script in its output
and (2) recovers the key command words.
"""

import re

import pytest

from core.textnorm import normalize_transcript, _has_non_latin


# The exact strings from the owner's screenshots (Devanagari/Telugu).
SCREENSHOT_CASES = [
    "ओपन WhatsApp एंड सेड मैसेज टु ऐश्वर्या सेइंग आई",   # open whatsapp and send message to aishwarya saying hi
    "सेंड मैसेज टू नवीन सेइंग हाउ आर यू",                 # send message to naveen saying how are you
    "సెంట్ హావర్ యు",                                     # (telugu) send how are you
    "ओपन वाट्सप अंड सेंड मेसेज टू नवीन",                   # open whatsapp and send message to naveen
]


@pytest.mark.parametrize("text", SCREENSHOT_CASES)
def test_output_is_pure_latin(text):
    """Core requirement: output must contain NO Indic/non-Latin script."""
    out = normalize_transcript(text)
    assert not _has_non_latin(out), f"output still has non-Latin script: {out!r}"
    # And it must be printable ASCII-ish (Latin letters/space/punct).
    assert re.fullmatch(r"[\x00-\x7F]*", out), f"output not ASCII: {out!r}"


def test_already_english_unchanged():
    for s in ["open chrome", "close whatsapp", "play a song on spotify", "Open Chrome."]:
        assert normalize_transcript(s) == s


def test_recovers_open_and_whatsapp():
    out = normalize_transcript("ओपन WhatsApp एंड सेड मैसेज टु ऐश्वर्या सेइंग आई").lower()
    assert "open" in out
    assert "whatsapp" in out
    assert "send" in out
    assert "message" in out
    assert "saying" in out


def test_recovers_send_message_how_are_you():
    out = normalize_transcript("सेंड मैसेज टू नवीन सेइंग हाउ आर यू").lower()
    assert "send" in out
    assert "message" in out
    assert "how are you" in out
    # The contact name survives as transliterated Latin (not snapped away).
    assert "nviin" in out or "naveen" in out or "navin" in out


def test_mixed_script_normalises():
    """A sentence mixing Latin ('WhatsApp') and Devanagari normalises wholly
    to Latin."""
    out = normalize_transcript("ओपन WhatsApp")
    assert not _has_non_latin(out)
    assert "open" in out.lower()
    assert "whatsapp" in out.lower()


def test_empty_and_none_safe():
    assert normalize_transcript("") == ""
    assert normalize_transcript(None) is None
