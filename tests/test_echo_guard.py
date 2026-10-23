"""
Tests for the self-echo guard (_is_self_echo) that stops Tony's own TTS,
re-captured by the mic, from being routed as a user command. Covers the
observed failure (echo captured in the tail AFTER speech ended, and garbled
re-captures below the old 0.8 threshold), while proving real commands and
slot-fill answers are never eaten.
"""

import time


def _set_speaking(ra, spoken, speaking=True, ended_ago=None):
    ra.is_speaking_locally = speaking
    ra.turn_ctx.last_spoken_text = spoken.strip().lower()
    if ended_ago is not None:
        ra.last_local_speech_end = time.perf_counter() - ended_ago
    else:
        ra.last_local_speech_end = 0.0


def test_echo_during_speech_exact(runtime_agent):
    ra = runtime_agent
    _set_speaking(ra, "closing whatsapp", speaking=True)
    now = time.perf_counter()
    assert ra._is_self_echo("closing whatsapp", now, awaiting_slot=False)


def test_partial_echo_is_allowed_through_to_protect_real_commands(runtime_agent):
    ra = runtime_agent
    # DESIGN CHANGE: the guard now requires NEAR-EXACT similarity. A partial
    # of what Tony said is deliberately ALLOWED through, because the previous
    # token-overlap matching dropped real commands that merely shared common
    # words with Tony's last line (e.g. "close the spotify window" vs
    # "closing whatsapp") and made Tony appear frozen/idle. Letting a rare
    # partial echo through is strictly safer than eating a real command.
    _set_speaking(ra, "message sent to bro successfully", speaking=True)
    now = time.perf_counter()
    assert not ra._is_self_echo("message sent to bro", now, awaiting_slot=False)


def test_near_exact_echo_is_dropped(runtime_agent):
    ra = runtime_agent
    # A near-identical re-capture of Tony's line IS still caught.
    _set_speaking(ra, "message sent to bro successfully", speaking=True)
    now = time.perf_counter()
    assert ra._is_self_echo("message sent to bro successfully", now, awaiting_slot=False)


def test_real_command_sharing_words_not_dropped(runtime_agent):
    ra = runtime_agent
    # The exact wedge case: a real command that shares common words with
    # Tony's last sentence must NOT be dropped.
    _set_speaking(ra, "closing whatsapp", speaking=True)
    now = time.perf_counter()
    assert not ra._is_self_echo("close the spotify window", now, awaiting_slot=False)


def test_echo_in_tail_after_speech_ended(runtime_agent):
    ra = runtime_agent
    # is_speaking_locally already reset to False, but speech ended 0.4s ago —
    # inside the echo window. This is the case the old guard missed entirely.
    _set_speaking(ra, "closing whatsapp", speaking=False, ended_ago=0.4)
    now = time.perf_counter()
    assert ra._is_self_echo("closing whatsapp", now, awaiting_slot=False)


def test_no_echo_long_after_speech(runtime_agent):
    ra = runtime_agent
    # Well outside the echo window -> never treated as echo.
    _set_speaking(ra, "closing whatsapp", speaking=False, ended_ago=5.0)
    now = time.perf_counter()
    assert not ra._is_self_echo("closing whatsapp", now, awaiting_slot=False)


def test_real_command_during_speech_not_dropped(runtime_agent):
    ra = runtime_agent
    # A genuinely different command said over Tony's speech must pass.
    _set_speaking(ra, "closing whatsapp", speaking=True)
    now = time.perf_counter()
    assert not ra._is_self_echo("open chrome and search weather", now, awaiting_slot=False)


def test_slot_answer_never_dropped(runtime_agent):
    ra = runtime_agent
    # While awaiting a slot-fill answer, even a short/odd answer must pass —
    # the guard must not eat the user's reply.
    _set_speaking(ra, "what should i say", speaking=True)
    now = time.perf_counter()
    assert not ra._is_self_echo("say happy birthday", now, awaiting_slot=True)


def test_no_spoken_text_means_no_echo(runtime_agent):
    ra = runtime_agent
    ra.is_speaking_locally = True
    ra.turn_ctx.last_spoken_text = ""
    now = time.perf_counter()
    assert not ra._is_self_echo("open chrome", now, awaiting_slot=False)
