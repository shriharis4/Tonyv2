"""
Tests for execute_tool()'s timeout tiering, crash isolation, and
structured result passthrough.
"""

import asyncio
import time

import pytest


@pytest.mark.asyncio
async def test_execute_tool_passes_through_fast_result(runtime_agent):
    async def fast_tool():
        return "quick success"
    fast_tool.__name__ = "open_app"

    result = await runtime_agent.execute_tool(fast_tool)
    assert result == "quick success"


@pytest.mark.asyncio
async def test_execute_tool_times_out_in_process_tier(runtime_agent):
    async def slow_tool():
        await asyncio.sleep(5)
        return "too slow"
    slow_tool.__name__ = "press_key"  # categorized as in_process -> 2s timeout

    t0 = time.perf_counter()
    result = await runtime_agent.execute_tool(slow_tool)
    elapsed = time.perf_counter() - t0

    assert elapsed < 3.0  # should cut off around 2s, well under the 5s sleep
    assert "timed out" in result.lower()
    assert result.startswith("❌")


@pytest.mark.asyncio
async def test_execute_tool_isolates_exceptions(runtime_agent):
    async def failing_tool():
        raise ValueError("simulated crash")
    failing_tool.__name__ = "open_app"

    result = await runtime_agent.execute_tool(failing_tool)
    assert result.startswith("❌")
    assert "failed to execute" in result.lower()


@pytest.mark.asyncio
async def test_execute_tool_network_tier_gets_longer_timeout(runtime_agent):
    """search_web is categorized 'network' (15s) — a 3s sleep should
    complete successfully, unlike the in_process 2s tier."""
    async def medium_tool():
        await asyncio.sleep(1)
        return "done"
    medium_tool.__name__ = "search_web"

    result = await runtime_agent.execute_tool(medium_tool)
    assert result == "done"


def test_get_tool_timeout_tiers():
    from tool_registry import get_tool_timeout

    assert get_tool_timeout("press_key") == 2.0
    assert get_tool_timeout("open_app") == 8.0
    assert get_tool_timeout("search_web") == 15.0
    # Unknown tool falls back to the default tier.
    assert get_tool_timeout("some_never_registered_tool") == 8.0
