"""
Shared pytest fixtures and mocks for the Tony test suite.

Tests here never perform real desktop automation, real system power
actions, real network calls, or real file deletion — all OS-level and
network-level calls are mocked. Rows in the spec's test matrix that
genuinely require a live Windows machine with LiveKit/hardware access are
marked and documented in tests/MANUAL_QA_CHECKLIST.md instead of being
faked here.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeSession:
    """Mimics the subset of LiveKit's AgentSession API the router touches."""

    def __init__(self):
        self.said = []
        self.interrupted = False
        self.cleared = False

    def interrupt(self, force: bool = False):
        self.interrupted = True

    def clear_user_turn(self):
        self.cleared = True

    async def say(self, text: str):
        self.said.append(text)

    async def generate_reply(self, **kwargs):
        return None


@pytest.fixture
def fake_session():
    return FakeSession()


@pytest.fixture
def runtime_agent(monkeypatch):
    """Import core.runtime_agent fresh-ish and reset shared router state
    between tests so pending_confirmation / turn_ctx from one test can't
    leak into another."""
    import core.runtime_agent as ra

    ra.turn_ctx.pending_confirmation = None
    ra.turn_ctx.state = "IDLE"
    ra.turn_ctx.last_handled_transcript = ""
    ra.turn_ctx.last_handled_at = 0.0
    ra.turn_ctx.last_processed_command = ""
    ra.turn_ctx.last_processed_at = 0.0
    ra.turn_ctx.last_spoken_text = ""
    ra.desktop_context["last_opened_app"] = None
    ra.desktop_context["last_referenced_file"] = None

    yield ra

    ra.turn_ctx.pending_confirmation = None
    ra.turn_ctx.state = "IDLE"
