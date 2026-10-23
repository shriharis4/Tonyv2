"""
Tests for the pre-routing noise guard (_looks_like_noise). VAD can trigger
on background sound and the STT then returns noise-only text; this guard
drops that before it is routed as a command. These cases are drawn from the
real noise rows observed in turn_timings plus the genuine short commands
that MUST still pass.
"""


# --- Noise that MUST be rejected --------------------------------------------

def test_rejects_empty_and_whitespace(runtime_agent):
    assert runtime_agent._looks_like_noise("")
    assert runtime_agent._looks_like_noise("   ")
    assert runtime_agent._looks_like_noise("\n\t ")


def test_rejects_pure_punctuation(runtime_agent):
    for s in [".", "...", "?", "!", ",", ". .", "-", "--"]:
        assert runtime_agent._looks_like_noise(s), f"should reject {s!r}"


def test_rejects_explicit_noise_markers(runtime_agent):
    for s in ["<noise>", "[noise]", "(noise)", "noise", "<inaudible>",
              "[inaudible]", "(music)", "silence", "blank_audio"]:
        assert runtime_agent._looks_like_noise(s), f"should reject {s!r}"


def test_rejects_single_stray_letter(runtime_agent):
    for s in ["a", "d", "k", "A", " m "]:
        assert runtime_agent._looks_like_noise(s), f"should reject {s!r}"


# --- Genuine commands that MUST pass ----------------------------------------

def test_passes_real_short_commands(runtime_agent):
    for s in ["open chrome", "close chrome", "Open Chrome.", "close Chrome",
              "open whatsapp", "play perfect on spotify",
              "what's 2 plus 4", "who is the father of the computer"]:
        assert not runtime_agent._looks_like_noise(s), f"should PASS {s!r}"


def test_passes_two_char_tokens(runtime_agent):
    # "hi", "ok", "go", "no" are legitimate two-letter utterances.
    for s in ["hi", "ok", "go", "no", "42"]:
        assert not runtime_agent._looks_like_noise(s), f"should PASS {s!r}"


def test_passes_garbled_multiword_command(runtime_agent):
    # Mis-transcribed but real multi-word intent must NOT be dropped here —
    # recovering these is textnorm's/VAD's job, not the noise guard's.
    assert not runtime_agent._looks_like_noise("klooj d kam viNddoo")
