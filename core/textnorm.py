"""
Transcript normalisation: force every transcript into Latin/English script.

The owner's STT (Gemini Live, Indian-accent English/Hinglish) returns
English speech written in Indic scripts (Devanagari/Telugu/Kannada/...),
so "open WhatsApp and send message to Aishwarya" arrives as
"ओपन WhatsApp एंड सेड मैसेज टु ऐश्वर्या". This module converts ANY
non-Latin transcript to Latin script and phonetically snaps the result
to real English command words, so both the chat bubble and the router
see English regardless of the language spoken.

Pipeline:
1. If the text is already pure ASCII, return it unchanged (fast path).
2. Transliterate non-Latin runs to Latin via `unidecode` (universal) with
   `indic_transliteration` as an optional higher-quality path for pure
   Devanagari.
3. Token-level phonetic "snap": fuzzy-match each transliterated token to a
   curated lexicon of ~150 command/Hinglish words so "opn"->"open",
   "maisej"->"message", "seiNg"->"saying", "ttu"->"to", "chalao"->"play".
"""

from __future__ import annotations

import difflib
import re

# --- optional deps, imported lazily / defensively ---
try:
    from unidecode import unidecode as _unidecode
except Exception:  # pragma: no cover
    _unidecode = None


# Command / Hinglish lexicon the snapper targets. Kept small and focused on
# words that actually matter to the router's intents.
_LEXICON = [
    # core verbs
    "open", "close", "exit", "launch", "start", "run", "play", "pause",
    "stop", "resume", "next", "previous", "send", "message", "text",
    "search", "find", "create", "make", "write", "type", "read", "delete",
    "rename", "move", "copy", "paste", "save", "scroll", "press", "click",
    "minimize", "maximize", "restore", "lock", "shutdown", "restart",
    "reboot", "sleep", "hibernate", "mute", "unmute", "increase", "decrease",
    "set", "take", "capture", "convert", "remind", "schedule", "show",
    "hide", "switch",
    # objects / targets
    "whatsapp", "spotify", "chrome", "browser", "notepad", "calculator",
    "excel", "word", "powerpoint", "explorer", "settings", "youtube",
    "volume", "brightness", "screenshot", "desktop", "file", "folder",
    "document", "song", "music", "email", "reminder", "weather", "news",
    "computer", "system", "screen", "window", "camera",
    # connectors / fillers
    "the", "a", "an", "to", "on", "in", "of", "and", "then", "please",
    "saying", "that", "about", "for", "with", "my", "me", "this", "it",
    "how", "are", "you", "what", "time", "date",
    # Hinglish command words
    "kholo", "khol", "band", "karo", "chalao", "bajao", "bhejo", "dikhao",
    "dhundo", "likho", "banao", "ruko", "bas", "haan", "nahi", "kam",
    "zyada", "ko", "pe", "par",
]

# Pre-build a lower-cased set for exact hits.
_LEXICON_SET = set(w.lower() for w in _LEXICON)

_LATIN_RE = re.compile(r"[^\u0000-\u024F\u1E00-\u1EFF]")  # anything outside basic+extended Latin


def _has_non_latin(text: str) -> bool:
    """True if the text contains characters outside the Latin ranges
    (i.e. Devanagari, Telugu, Kannada, Tamil, Arabic, etc.)."""
    return bool(_LATIN_RE.search(text or ""))


def _transliterate(text: str) -> str:
    """Convert any non-Latin script to Latin. unidecode handles every
    script and mixed-script text gracefully; we keep already-Latin runs
    as-is."""
    if _unidecode is None:
        return text
    try:
        return _unidecode(text)
    except Exception:
        return text


# Direct phonetic aliases for common unidecode outputs of Hinglish/Indic
# transliterations that difflib won't reliably snap (too mangled). Mapped
# BEFORE fuzzy matching. Keys are lower-cased unidecode output tokens.
_PHONETIC_ALIASES = {
    "opn": "open", "opan": "open", "opun": "open",
    "klos": "close", "kloz": "close", "band": "close",
    "maisej": "message", "masej": "message", "mesej": "message",
    "mesij": "message", "maisaj": "message", "msej": "message",
    "send": "send", "sed": "send", "seind": "send", "sedd": "send",
    "sendd": "send", "saind": "send",
    "seing": "saying", "seng": "saying", "seyng": "saying",
    "ttu": "to", "tu": "to", "too": "to", "ttuu": "to", "tuu": "to",
    "endd": "and", "end": "and", "aur": "and",
    "haau": "how", "hau": "how", "hav": "how", "havr": "how",
    "ar": "are", "aar": "are",
    "yu": "you", "yuu": "you", "yoo": "you",
    "aai": "hi", "aaii": "hi", "hai": "hi",
    "chalao": "play", "bajao": "play", "chala": "play",
    "kholo": "open", "khol": "open",
    "bhejo": "send", "bhej": "send",
    "dhundo": "search", "dhundho": "search",
    "likho": "write", "likh": "write",
    "banao": "create", "bana": "create",
    "ruko": "stop", "bas": "stop",
    "vatsap": "whatsapp", "vhatsap": "whatsapp", "watsap": "whatsapp",
    "spotifai": "spotify", "spotify": "spotify",
    "krom": "chrome", "krome": "chrome", "kroom": "chrome",
    "gaana": "song", "gana": "song", "geet": "song",
    "faail": "file", "fail": "file",
    "voliyum": "volume", "volyum": "volume",
}


def _snap_token(token: str) -> str:
    """Fuzzy-snap a single transliterated token to the nearest command-word
    in the lexicon, if close enough. Leaves unknown tokens (names, free
    text) unchanged."""
    low = token.lower()
    if not low or not low.isalpha():
        return token
    if low in _LEXICON_SET:
        return low
    # Explicit phonetic alias table first (handles mangled forms difflib
    # can't reach).
    if low in _PHONETIC_ALIASES:
        return _PHONETIC_ALIASES[low]
    # difflib close match; cutoff tuned so real words snap but names don't.
    match = difflib.get_close_matches(low, _LEXICON_SET, n=1, cutoff=0.8)
    if match:
        return match[0]
    return token


def normalize_transcript(text: str, snap: bool = True) -> str:
    """
    Return the transcript in Latin/English script.

    - Pure-ASCII input is returned unchanged (fast path).
    - Non-Latin input is transliterated to Latin, then (if `snap`) each
      token is fuzzy-snapped to the command lexicon so obvious command
      words are recovered.

    This is intentionally conservative: it never drops tokens and only
    rewrites a token when a close lexicon match exists, so contact/song/
    file names (which won't match the lexicon) survive as transliterated
    Latin text.
    """
    if not text:
        return text
    if not _has_non_latin(text):
        return text  # already English/Latin

    latin = _transliterate(text)
    if not snap:
        return latin

    out_tokens = []
    for tok in latin.split():
        # Preserve leading/trailing punctuation around the token.
        m = re.match(r"^(\W*)(.*?)(\W*)$", tok, re.DOTALL)
        if not m:
            out_tokens.append(tok)
            continue
        pre, core, post = m.group(1), m.group(2), m.group(3)
        out_tokens.append(pre + _snap_token(core) + post)
    return " ".join(out_tokens)
