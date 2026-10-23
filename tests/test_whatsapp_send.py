"""
Tests for the VERIFIED WhatsApp send flow (Tools/send_whatsapp_message).

The fake UI below mirrors what WhatsApp Desktop actually exposes through UI
Automation on this machine (probed live): a "Search or start a new chat"
edit box, result rows like "Bro 11:19 am Hello" under Chats/Contacts, and a
composer named "Type a message to <Contact>" whose value can be read back.

Covers the reported bugs: wrong/no contact found but Tony said "Message
sent"; text typed into the search box; keystrokes outside WhatsApp.
"""

import pytest

import Tools.send_whatsapp_message as wa


@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch):
    monkeypatch.setattr(wa, "FOCUS_TIMEOUT", 0.05)
    monkeypatch.setattr(wa, "RESULTS_TIMEOUT", 0.05)
    monkeypatch.setattr(wa, "CHAT_OPEN_TIMEOUT", 0.05)
    monkeypatch.setattr(wa, "VERIFY_TIMEOUT", 0.05)
    monkeypatch.setattr(wa, "POLL", 0.01)


class FakeWhatsApp:
    def __init__(self, chats, foreground=True, send_works=True, paste_works=True):
        self.chats = chats            # list of row names, e.g. "Bro 11:19 am Hello"
        self.foreground = foreground
        self.send_works = send_works
        self.paste_works = paste_works
        self.search_text = ""
        self.open_chat = None
        self.composer = ""
        self.sent = []                # (chat, text)
        self.log = []
        self._rows = []

    def launch(self): self.log.append("launch")
    def is_foreground(self): return self.foreground

    def search(self, text):
        self.search_text = text
        self.log.append(("search", text))
        return True

    def clear_search(self):
        self.search_text = ""
        self.log.append("clear_search")

    def chat_rows(self):
        q = self.search_text.lower()
        self._rows = [c for c in self.chats if q and q in c.lower()]
        return list(self._rows)

    def open_row(self, i):
        self.open_chat = wa.row_contact_name(self._rows[i])
        self.log.append(("open", self.open_chat))
        return True

    def composer_name(self):
        return f"Type a message to {self.open_chat}" if self.open_chat else None

    def composer_text(self): return self.composer

    def paste_into_composer(self, text):
        self.log.append(("paste", text))
        if self.paste_works:
            self.composer += text
        return True

    def press_enter(self):
        self.log.append("enter")
        if self.send_works and self.composer:
            self.sent.append((self.open_chat, self.composer))
            self.composer = ""


CHATS = ["Bro 11:19 am Hello", "NoBroker.com 11/03/2026 secure service", "Naveen 13/10/2026 Bro, money?"]


def test_sends_to_exact_contact_and_reports_success():
    ui = FakeWhatsApp(CHATS)
    res = wa.send_flow(ui, "bro", "hi")
    assert ui.sent == [("Bro", "hi")]
    assert res.startswith("✅") and "Bro" in res


def test_unknown_contact_sends_nothing_and_fails_with_suggestions():
    ui = FakeWhatsApp(CHATS)
    res = wa.send_flow(ui, "gro", "hi")       # STT turned "bro" into "gro"
    assert ui.sent == []
    assert not any(isinstance(a, tuple) and a[0] == "paste" for a in ui.log)
    assert res.startswith("❌") and "nothing was sent" in res
    assert "clear_search" in ui.log


def test_no_search_results_reports_failure_not_success():
    ui = FakeWhatsApp([])
    res = wa.send_flow(ui, "bro", "hi")
    assert ui.sent == [] and res.startswith("❌")


def test_does_not_pick_a_partial_match_like_nobroker():
    ui = FakeWhatsApp(["NoBroker.com 11/03/2026 x", "Brother Ji 10:00 am y"])
    res = wa.send_flow(ui, "bro", "hi")
    assert ui.sent == [] and res.startswith("❌")


def test_close_spelling_still_matches_unique_contact():
    ui = FakeWhatsApp(["Naveen 13/10/2026 x", "Bro 11:19 am y"])
    res = wa.send_flow(ui, "naveen", "hello")
    assert ui.sent == [("Naveen", "hello")] and res.startswith("✅")


def test_message_never_goes_into_search_box():
    ui = FakeWhatsApp(CHATS)
    wa.send_flow(ui, "bro", "hi")
    searches = [a[1] for a in ui.log if isinstance(a, tuple) and a[0] == "search"]
    assert searches == ["bro"], searches


def test_nothing_happens_when_whatsapp_not_in_front():
    ui = FakeWhatsApp(CHATS, foreground=False)
    res = wa.send_flow(ui, "bro", "hi")
    assert ui.sent == [] and res.startswith("❌")
    assert not any(isinstance(a, tuple) for a in ui.log), ui.log  # no search/paste


def test_send_not_confirmed_is_reported_as_failure():
    ui = FakeWhatsApp(CHATS, send_works=False)
    res = wa.send_flow(ui, "bro", "hi")
    assert res.startswith("❌") and "did not confirm" in res


def test_text_not_appearing_in_composer_is_not_sent():
    ui = FakeWhatsApp(CHATS, paste_works=False)
    res = wa.send_flow(ui, "bro", "hi")
    assert ui.sent == [] and "enter" not in ui.log and res.startswith("❌")


def test_empty_contact_or_message_fail_fast():
    assert wa.send_flow(FakeWhatsApp(CHATS), "", "hi").startswith("❌")
    assert wa.send_flow(FakeWhatsApp(CHATS), "bro", "").startswith("❌")


@pytest.mark.parametrize("row,name", [
    ("Bro 11:19 am Hello", "Bro"),
    ("NoBroker.com 11/03/2026 This business", "NoBroker.com"),
    ("Mom Yesterday ok", "Mom"),
    ("Basvaraj Cse 15/10/2026 Nange", "Basvaraj Cse"),
])
def test_row_contact_name(row, name):
    assert wa.row_contact_name(row) == name
