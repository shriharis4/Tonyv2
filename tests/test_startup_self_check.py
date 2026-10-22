"""
Tests for the startup self-check (core.runtime_agent._run_startup_self_check).
"""

import pytest


def test_startup_self_check_never_raises(runtime_agent):
    """The self-check must be purely diagnostic - it should never raise
    or block startup, even if credentials/permissions are missing."""
    runtime_agent._run_startup_self_check()  # should not raise


def test_startup_self_check_detects_missing_livekit_creds(runtime_agent, monkeypatch, caplog):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)

    import logging
    with caplog.at_level(logging.WARNING, logger="tony.router"):
        runtime_agent._run_startup_self_check()

    assert any("LiveKit credentials missing" in r.message for r in caplog.records)


def test_startup_self_check_detects_missing_google_api_key(runtime_agent, monkeypatch, caplog):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    import logging
    with caplog.at_level(logging.WARNING, logger="tony.router"):
        runtime_agent._run_startup_self_check()

    assert any("GOOGLE_API_KEY" in r.message for r in caplog.records)
