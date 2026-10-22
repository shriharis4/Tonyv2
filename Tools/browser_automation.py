"""
Real browser automation (Playwright-backed) for navigating pages and
filling forms — distinct from `search_web.py`/`webScrping.py`, which only
search/scrape and never interact with a live page.

Uses a single persistent Chromium context (launched lazily, lives for the
process lifetime) so sequential multi-step flows (navigate -> fill -> click)
can share state like login cookies within a session.
"""

from __future__ import annotations

import asyncio
from typing import Literal, Optional

from livekit.agents import function_tool

from Tools.tool_result import ok, fail

_playwright = None
_browser = None
_page = None
_lock = asyncio.Lock()


async def _ensure_page():
    global _playwright, _browser, _page
    if _page is not None:
        return _page

    from playwright.async_api import async_playwright

    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=False)
    context = await _browser.new_context()
    _page = await context.new_page()
    return _page


@function_tool()
async def browser_automate(
    action: Literal["navigate", "fill", "click", "extract_text", "close"],
    target: str,
    value: Optional[str] = None,
) -> str:
    """
    Navigate and interact with web pages using a real browser (Playwright),
    for tasks search/scrape tools can't do: filling forms, clicking
    through multi-step flows, and reading rendered page content.

    Args:
        action: "navigate" (target=URL), "fill" (target=CSS selector,
            value=text to type), "click" (target=CSS selector),
            "extract_text" (target=CSS selector, or "body" for the whole
            page), or "close" (shuts down the browser session).
        target: URL for navigate, CSS selector for fill/click/extract_text,
            ignored for close.
        value: Text to type, required for "fill".

    Returns:
        Structured success/failure string. Login-walled pages return a
        clear message instead of hanging.
    """
    try:
        async with _lock:
            if action == "close":
                global _browser, _playwright, _page
                if _browser:
                    await _browser.close()
                if _playwright:
                    await _playwright.stop()
                _browser = None
                _playwright = None
                _page = None
                return ok("Browser session closed.")

            page = await _ensure_page()

            if action == "navigate":
                if not target:
                    return fail("No URL provided.")
                url = target if target.startswith(("http://", "https://")) else f"https://{target}"
                await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                title = await page.title()
                return ok(f"Navigated to {url}", detail=f"title={title}")

            if action == "fill":
                if value is None:
                    return fail("No value provided to fill.")
                await page.fill(target, value, timeout=8000)
                return ok(f"Filled '{target}' with provided value")

            if action == "click":
                await page.click(target, timeout=8000)
                return ok(f"Clicked '{target}'")

            if action == "extract_text":
                selector = target or "body"
                content = await page.inner_text(selector, timeout=8000)
                snippet = content.strip()[:1000]
                return ok("Extracted page text", detail=snippet)

            return fail(f"Unknown action '{action}'.")

    except ImportError:
        return fail(
            "Playwright is required for browser automation.",
            detail="pip install playwright && playwright install chromium",
        )
    except Exception as e:
        msg = str(e)
        if "Timeout" in msg or "timeout" in msg:
            return fail(
                f"Action '{action}' timed out on '{target}'.",
                detail="Page may require login or the selector doesn't exist.",
            )
        return fail(f"Browser action '{action}' failed", detail=msg)
