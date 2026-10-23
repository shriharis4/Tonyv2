"""
WhatsApp Desktop message sender — VERIFIED flow.

Every step is checked against WhatsApp's real UI (Windows UI Automation)
before the next one runs, and success is only reported when WhatsApp itself
shows it:

  1. open/focus WhatsApp via the 'whatsapp:' protocol (no typing into
     Windows search)
  2. put the contact name into "Search or start a new chat" (set directly,
     not typed key-by-key)
  3. read the search results and pick the chat whose NAME matches the
     contact (exact, or a very close unique match). If none matches, stop
     and return the closest names -> nothing is sent to the wrong person
  4. open that chat and confirm the composer reads "Type a message to
     <that contact>"
  5. paste the message, read the composer back to confirm the exact text
  6. press Enter and confirm the composer emptied (message left the box)

Any failed check returns a ❌ result, so Tony never says "message sent"
when it wasn't.
"""

from __future__ import annotations

import difflib
import os
import re
import time
from typing import List, Optional, Tuple

import asyncio
import pyautogui
from livekit.agents import function_tool

try:
    from Tools.tool_result import ok, fail
except Exception:  # pragma: no cover - import path fallback
    from tool_result import ok, fail

# Poll timeouts (seconds). Tests shrink these.
FOCUS_TIMEOUT = 8.0
RESULTS_TIMEOUT = 3.0
CHAT_OPEN_TIMEOUT = 4.0
VERIFY_TIMEOUT = 2.0
POLL = 0.15
FUZZY_MIN = 0.85

_TIME_OR_DATE = re.compile(
    r"\s+(?:\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}/\d{1,2}/\d{2,4}|yesterday|today|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


def row_contact_name(row_name: str) -> str:
    """'Bro 11:19 am Hello' -> 'Bro'; 'NoBroker.com 11/03/2026 ...' -> 'NoBroker.com'."""
    row_name = (row_name or "").strip()
    m = _TIME_OR_DATE.search(row_name)
    return (row_name[: m.start()] if m else row_name).strip()


def pick_contact(contact: str, row_names: List[str]) -> Tuple[Optional[int], List[str]]:
    """Return (index of the matching chat row or None, closest names).
    Exact (case-insensitive) name match wins; otherwise a single close
    fuzzy match (>= FUZZY_MIN); otherwise no match (never guess)."""
    want = contact.strip().lower()
    names = [row_contact_name(r) for r in row_names]
    exact = [i for i, n in enumerate(names) if n.lower() == want]
    if exact:
        return exact[0], []
    scored = sorted(
        ((difflib.SequenceMatcher(None, want, n.lower()).ratio(), i) for i, n in enumerate(names)),
        reverse=True,
    )
    close = [(s, i) for s, i in scored if s >= FUZZY_MIN]
    if len(close) == 1 or (len(close) > 1 and close[0][0] - close[1][0] >= 0.1):
        return close[0][1], []
    suggestions = []
    for s, i in scored:
        if s >= 0.5 and names[i] not in suggestions:
            suggestions.append(names[i])
    return None, suggestions[:3]


def _wait(pred, timeout: float):
    end = time.monotonic() + timeout
    while True:
        v = pred()
        if v:
            return v
        if time.monotonic() >= end:
            return v
        time.sleep(POLL)


def _ensure_foreground(ui) -> bool:
    """WhatsApp must be the active window before any input. Focus can blip
    briefly while the 'whatsapp:' activation settles, so wait a moment and
    re-activate once instead of failing on a single check."""
    if _wait(ui.is_foreground, min(1.0, FOCUS_TIMEOUT)):
        return True
    ui.launch()
    return bool(_wait(ui.is_foreground, FOCUS_TIMEOUT))


# ---------------------------------------------------------------------------
# Real UI driver (Windows UI Automation via comtypes)
# ---------------------------------------------------------------------------
class RealWhatsAppUI:
    SEARCH_NAME = "Search or start a new chat"

    def __init__(self):
        import comtypes
        import comtypes.client
        comtypes.CoInitialize()
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as U
        self.U = U
        self.uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
        self._root = None

    def close(self):
        try:
            import comtypes
            comtypes.CoUninitialize()
        except Exception:
            pass

    # -- window ----------------------------------------------------------
    def _hwnd(self):
        import win32gui, win32process, psutil
        found = []

        def cb(h, _):
            if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h):
                try:
                    pid = win32process.GetWindowThreadProcessId(h)[1]
                    if "whatsapp" in psutil.Process(pid).name().lower():
                        found.append(h)
                except Exception:
                    pass
            return True

        win32gui.EnumWindows(cb, None)
        return found[0] if found else None

    def launch(self):
        """Open WhatsApp and bring it to the front. Windows blocks a
        background process from taking focus, so after the protocol launch
        we restore the window and use the standard AttachThreadInput +
        Alt-tap workaround to make it the foreground window."""
        os.startfile("whatsapp:")
        h = _wait(self._hwnd, 6.0)
        if not h:
            return
        try:
            import win32gui, win32con, win32process, win32api
            if win32gui.IsIconic(h):
                win32gui.ShowWindow(h, win32con.SW_RESTORE)
            fg = win32gui.GetForegroundWindow()
            cur = win32api.GetCurrentThreadId()
            fg_thread = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
            attached = False
            if fg_thread and fg_thread != cur:
                attached = bool(win32process.AttachThreadInput(cur, fg_thread, True))
            try:
                # Alt tap (no key is typed into any app) unlocks SetForegroundWindow.
                win32api.keybd_event(0x12, 0, 0, 0)
                win32api.keybd_event(0x12, 0, 2, 0)
                win32gui.BringWindowToTop(h)
                win32gui.SetForegroundWindow(h)
            finally:
                if attached:
                    win32process.AttachThreadInput(cur, fg_thread, False)
        except Exception:
            pass

    def is_foreground(self) -> bool:
        try:
            import win32gui, win32process, psutil
            h = win32gui.GetForegroundWindow()
            pid = win32process.GetWindowThreadProcessId(h)[1]
            return "whatsapp" in psutil.Process(pid).name().lower()
        except Exception:
            return False

    def _root_el(self):
        h = self._hwnd()
        return self.uia.ElementFromHandle(h) if h else None

    def _doc(self):
        """WhatsApp's web content root. Querying inside it is ~0.03s;
        querying the whole window walks the browser shell and took ~7s."""
        root = self._root_el()
        if root is None:
            return None
        doc = root.FindFirst(self.U.TreeScope_Descendants, self.uia.CreatePropertyCondition(
            self.U.UIA_AutomationIdPropertyId, "RootWebArea"))
        return doc or root

    def _find_all(self, cond):
        doc = self._doc()
        if doc is None:
            return []
        arr = doc.FindAll(self.U.TreeScope_Descendants, cond)
        return [arr.GetElement(i) for i in range(arr.Length)]

    def _value(self, el) -> str:
        try:
            vp = el.GetCurrentPattern(self.U.UIA_ValuePatternId)
            return vp.QueryInterface(self.U.IUIAutomationValuePattern).CurrentValue or ""
        except Exception:
            return ""

    def _edits(self):
        return self._find_all(self.uia.CreatePropertyCondition(
            self.U.UIA_ControlTypePropertyId, self.U.UIA_EditControlTypeId))

    def _name(self, el) -> str:
        try:
            return el.CurrentName or ""
        except Exception:
            return ""

    # -- search ----------------------------------------------------------
    def _search_box(self):
        # Its name ("Search or start a new chat") is only present while the
        # box is empty, so pick the first edit that isn't the chat composer.
        for e in self._edits():
            if not self._name(e).startswith("Type a message"):
                return e
        return None

    def search(self, text: str) -> bool:
        box = self._search_box()
        if box is None:
            return False
        box.SetFocus()
        vp = box.GetCurrentPattern(self.U.UIA_ValuePatternId).QueryInterface(self.U.IUIAutomationValuePattern)
        vp.SetValue(text)
        return True

    def clear_search(self):
        try:
            self.search("")
        except Exception:
            pass

    def chat_rows(self) -> List[str]:
        """Names of result rows in the Chats/Contacts sections (stops at the
        'Messages' section, which lists message hits, not chats)."""
        self._rows = []
        rows = self._find_all(self.uia.CreatePropertyCondition(
            self.U.UIA_ControlTypePropertyId, self.U.UIA_DataItemControlTypeId))
        out, section = [], None
        for r in rows:
            try:
                name = (r.CurrentName or "").strip()
            except Exception:
                continue  # row vanished while the list was updating
            low = name.lower()
            if low in ("chats", "contacts", "groups", "messages"):
                section = low
                continue
            if section in ("chats", "contacts", "groups") and name and name not in out:
                out.append(name)
                self._rows.append(r)
        return out

    def open_row(self, index: int) -> bool:
        r = self._rows[index]
        rc = r.CurrentBoundingRectangle
        if rc.right <= rc.left or rc.bottom <= rc.top:
            return False
        pyautogui.click((rc.left + rc.right) // 2, (rc.top + rc.bottom) // 2)
        return True

    # -- composer ------------------------------------------------------------
    def _composer(self):
        for e in self._edits():
            if self._name(e).startswith("Type a message"):
                return e
        return None

    def composer_name(self) -> Optional[str]:
        c = self._composer()
        return self._name(c) if c is not None else None

    def composer_text(self) -> str:
        c = self._composer()
        return self._value(c).strip() if c is not None else ""

    def paste_into_composer(self, text: str) -> bool:
        """Paste via the clipboard (handles any characters, instant). The
        user's clipboard is restored only AFTER WhatsApp shows the text -
        WhatsApp reads the clipboard asynchronously, and restoring it after
        a fixed 0.25s made it paste the OLD clipboard (verified live)."""
        import win32clipboard
        c = self._composer()
        if c is None:
            return False
        c.SetFocus()
        old = None
        try:
            win32clipboard.OpenClipboard()
            try:
                old = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            except Exception:
                old = None
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        pyautogui.hotkey("ctrl", "v")
        _wait(lambda: self.composer_text() == text.strip(), VERIFY_TIMEOUT)
        if old is not None:
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(old, win32clipboard.CF_UNICODETEXT)
            except Exception:
                pass
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
        return True

    def press_enter(self):
        pyautogui.press("enter")


# ---------------------------------------------------------------------------
# Verified send flow (pure logic; works with the real or a fake UI driver)
# ---------------------------------------------------------------------------
def send_flow(ui, contact: str, message: str) -> str:
    contact = (contact or "").strip()
    message = (message or "").strip()
    if not contact:
        return fail("No WhatsApp contact name was given.")
    if not message:
        return fail(f"No message text was given for {contact}.")

    # 1. open + focus
    ui.launch()
    if not _ensure_foreground(ui):
        return fail("WhatsApp did not come to the front; nothing was typed.")

    # 2-3. search and pick the exact chat
    if not ui.search(contact):
        return fail("Could not find WhatsApp's search box; nothing was sent.")
    rows = _wait(ui.chat_rows, RESULTS_TIMEOUT) or []
    idx, suggestions = pick_contact(contact, rows)
    if idx is None:
        ui.clear_search()
        hint = f" Closest names: {', '.join(suggestions)}." if suggestions else ""
        return fail(f"No WhatsApp chat named '{contact}' was found, so nothing was sent.{hint}")
    chat_name = row_contact_name(rows[idx])

    # 4. open the chat and confirm it's the right one
    if not _ensure_foreground(ui):
        return fail("WhatsApp lost focus before opening the chat; nothing was sent.")
    if not ui.open_row(idx):
        return fail(f"Could not open the chat with {chat_name}; nothing was sent.")
    opened = _wait(lambda: (ui.composer_name() or "").lower().endswith(f"to {chat_name.lower()}"),
                   CHAT_OPEN_TIMEOUT)
    if not opened:
        return fail(f"The chat with {chat_name} did not open; nothing was sent.")

    # 5. put the message in and verify it exactly
    if ui.composer_text():
        return fail(f"The message box for {chat_name} already had a draft; nothing was sent.")
    if not _ensure_foreground(ui) or not ui.paste_into_composer(message):
        return fail(f"Could not type into the chat with {chat_name}; nothing was sent.")
    if not _wait(lambda: ui.composer_text() == message, VERIFY_TIMEOUT):
        return fail(f"The message text did not appear correctly for {chat_name}; it was not sent.")

    # 6. send and confirm the box emptied
    if not _ensure_foreground(ui):
        return fail(f"WhatsApp lost focus before sending to {chat_name}; the message was not sent.")
    ui.press_enter()
    if not _wait(lambda: ui.composer_text() == "", VERIFY_TIMEOUT):
        return fail(f"WhatsApp did not confirm the message to {chat_name} was sent.")
    return ok(f"Message sent to {chat_name}: \"{message}\"")


def _send_blocking(contact: str, message: str) -> str:
    ui = RealWhatsAppUI()
    try:
        return send_flow(ui, contact, message)
    except Exception as e:
        return fail("WhatsApp automation failed; the message may not have been sent.", detail=str(e))
    finally:
        ui.close()


@function_tool()
async def send_whatsapp_message(contact: str, message: str, mode: str = "balanced") -> str:
    """
    Send a WhatsApp message to a saved contact or chat. Verifies the right
    chat is open and the message actually left the box before reporting
    success; returns a failure (with closest contact names) otherwise.

    Args:
        contact: Contact or chat name exactly as saved in WhatsApp
        message: Message text to send
        mode: Kept for compatibility; ignored
    """
    return await asyncio.to_thread(_send_blocking, contact, message)


@function_tool()
async def send_whatsapp_message_advanced(contact: str, message: str) -> str:
    """Legacy alias of send_whatsapp_message."""
    return await asyncio.to_thread(_send_blocking, contact, message)
