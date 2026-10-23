"""
Routing tests for combined "open whatsapp and send message ..." commands.

Real-run evidence (turn_timings 10:07): "open whatsapp and send message to
bro saying how are you" ran a 0.11s tool and Tony said "Opening Whatsapp." —
the open-app intent swallowed the command and the message was never sent.
These tests pin the correct behaviour: the SEND intent must win.
"""

import pytest


def _patch(monkeypatch, ra, name):
    calls = []

    async def _fake(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    _fake.__name__ = name
    monkeypatch.setattr(ra, name, _fake)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("cmd,contact,msg", [
    ("open whatsapp and send message to bro saying how are you", "bro", "how are you"),
    ("open whatsapp and send a message to naveen saying hello", "naveen", "hello"),
    ("whatsapp and send message to bro saying hello", "bro", "hello"),
    ("send message to bro saying how are you", "bro", "how are you"),
    ("launch whatsapp and text bro saying hi there", "bro", "hi there"),
    ("send message on whatsapp to bro saying hi", "bro", "hi"),
    ("send a whatsapp message to bro saying good morning", "bro", "good morning"),
    ("open whatsapp and send message to gro saying haaii", "gro", "haaii"),
])
async def test_combined_open_and_send_routes_to_send(runtime_agent, fake_session, monkeypatch, cmd, contact, msg):
    ra = runtime_agent
    send_calls = _patch(monkeypatch, ra, "send_whatsapp_message")
    open_calls = _patch(monkeypatch, ra, "open_app")
    handled = await ra.route_command_directly(fake_session, cmd)
    assert handled is True
    assert send_calls == [((contact, msg), {})], f"send not called correctly for {cmd!r}: {send_calls}"
    # The send tool opens WhatsApp itself; a separate open_app call would
    # steal focus / duplicate the launch.
    assert open_calls == [], f"open_app should not run for {cmd!r}: {open_calls}"


@pytest.mark.asyncio
async def test_plain_open_whatsapp_still_opens(runtime_agent, fake_session, monkeypatch):
    ra = runtime_agent
    send_calls = _patch(monkeypatch, ra, "send_whatsapp_message")
    open_calls = _patch(monkeypatch, ra, "open_app")
    handled = await ra.route_command_directly(fake_session, "open whatsapp")
    assert handled is True
    assert send_calls == []
    assert len(open_calls) == 1
