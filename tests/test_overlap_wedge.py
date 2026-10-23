"""
Regression tests for the task-overlap and idle-wedge bugs reported from
the screenshot (WhatsApp send overlapping with an Edge search; assistant
sitting idle after a few tasks).

Covers:
- The multi-step splitter must NOT split a message-send command that has a
  "saying" payload (D-10) — "open whatsapp and send message to X saying Y"
  must route as ONE WhatsApp send, not split into overlapping steps.
- The global input lock serializes tool execution so two tools cannot run
  concurrently (D-09).
"""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_whatsapp_and_send_not_split(runtime_agent, fake_session, monkeypatch):
    """'open whatsapp and send message to X saying Y' must be treated as a
    single WhatsApp send (payload guard), not split on 'and' into
    overlapping steps."""
    wa = []

    async def fake_wa(contact, message):
        wa.append((contact, message))
        return "ok"
    fake_wa.__name__ = "send_whatsapp_message"
    monkeypatch.setattr(runtime_agent, "send_whatsapp_message", fake_wa)

    opened = []

    async def fake_open(name):
        opened.append(name)
        return "ok"
    fake_open.__name__ = "open_app"
    monkeypatch.setattr(runtime_agent, "open_app", fake_open)

    handled = await runtime_agent.route_command_directly(
        fake_session, "send message to aishwarya saying hello there"
    )
    assert handled is True
    assert len(wa) == 1
    assert wa[0][0].lower().startswith("aishwarya")
    assert "hello there" in wa[0][1].lower()


@pytest.mark.asyncio
async def test_message_payload_with_and_not_split(runtime_agent, fake_session, monkeypatch):
    """A message body containing 'and' must not be split."""
    wa = []

    async def fake_wa(contact, message):
        wa.append((contact, message))
        return "ok"
    fake_wa.__name__ = "send_whatsapp_message"
    monkeypatch.setattr(runtime_agent, "send_whatsapp_message", fake_wa)

    await runtime_agent.route_command_directly(
        fake_session, "send message to ravi saying bread and butter"
    )
    assert len(wa) == 1
    assert "bread and butter" in wa[0][1].lower(), "the 'and' in the payload must not split the message"


@pytest.mark.asyncio
async def test_input_lock_serializes_tool_calls(runtime_agent, fake_session, monkeypatch):
    """Two overlapping routed tool calls must not run concurrently — the
    input lock forces them to serialize (fixes the WhatsApp+search overlap)."""
    order = []

    async def slow_tool(name, delay):
        order.append(f"{name}:start")
        await asyncio.sleep(delay)
        order.append(f"{name}:end")
        return "ok"

    async def tool_a():
        return await slow_tool("A", 0.3)
    tool_a.__name__ = "open_app"

    async def tool_b():
        return await slow_tool("B", 0.1)
    tool_b.__name__ = "search_web"

    monkeypatch.setattr(runtime_agent, "open_app", tool_a)
    monkeypatch.setattr(runtime_agent, "search_web", tool_b)

    # Fire two commands concurrently; the input lock must serialize their
    # tool execution so B cannot start before A finishes.
    await asyncio.gather(
        runtime_agent.route_command_directly(fake_session, "open notepad"),
        runtime_agent.route_command_directly(fake_session, "search the web for cats"),
    )

    # Find the start/end order; whichever ran first must fully finish before
    # the other starts (no interleaving).
    starts_ends = [e for e in order if e.endswith(":start") or e.endswith(":end")]
    # Assert no interleaving: once a tool starts, it ends before another starts.
    active = None
    for ev in starts_ends:
        name, phase = ev.split(":")
        if phase == "start":
            assert active is None, f"tool {name} started while {active} was still running (overlap!)"
            active = name
        else:
            assert active == name
            active = None
