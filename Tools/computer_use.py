"""General desktop fallback when a request does not match a dedicated Tools/ module."""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
import webbrowser
from typing import Literal

from livekit.agents import function_tool

from Tools.tool_result import ok, fail

_BLOCKED = re.compile(
    r"(\bdel\b|\berase\b|rmdir|rm\s+-rf|format\s+|diskpart|"
    r"shutdown|restart|reboot|hibernate|reg\s+delete|"
    r"Remove-Item|Format-Volume|cipher\s+/w)",
    re.IGNORECASE,
)


def _blocked(text: str) -> bool:
    return bool(_BLOCKED.search(text or ""))


@function_tool()
async def perform_computer_action(
    action: Literal["launch", "type", "hotkey", "click", "click_text", "open_url", "open_path"],
    detail: str,
) -> str:
    """
    Carry out a reasonable desktop action that has no dedicated tool.

    Safety: refuses destructive file deletion, disk format, and system power
    commands. Use system_power_action for shutdown/restart/lock/sleep.

    Args:
        action: One of "launch", "type", "hotkey", "click" (raw x,y
            coordinates), "click_text" (OCR-based: click a UI element by
            its visible text label, e.g. "click the Save button" ->
            action="click_text", detail="Save"), "open_url", "open_path".
        detail: Action-specific payload — see `action` above.
    """
    detail = (detail or "").strip()
    if not detail:
        return fail("Need a concrete action detail.")
    if _blocked(detail):
        return fail(
            "Blocked: destructive or power operations must use the dedicated "
            "system_power_action tool after the existing confirmation pattern."
        )

    loop = asyncio.get_running_loop()

    if action == "open_url":
        url = detail if re.match(r"^https?://", detail, re.I) else f"https://{detail}"
        await loop.run_in_executor(None, webbrowser.open, url)
        return ok(f"Opened {url}")

    if action == "open_path":
        path = os.path.expandvars(os.path.expanduser(detail))
        if not os.path.exists(path):
            return fail(f"Path not found: {path}")
        await loop.run_in_executor(None, os.startfile, path)
        return ok(f"Opened {path}")

    if action == "launch":
        # Injection-safe launch (fixes D-16/H-13): never compose a shell
        # string from model/user text. `os.startfile` resolves app names,
        # file paths, and registered protocols without a shell; if it fails
        # for a bare executable, fall back to Popen with an ARGV LIST
        # (shell=False), so `detail` is always a single, un-split argument
        # and cannot inject additional commands.
        target = detail.strip().strip('"')
        try:
            await loop.run_in_executor(None, os.startfile, target)
            return ok(f"Launched {target}")
        except Exception:
            try:
                await loop.run_in_executor(None, lambda: subprocess.Popen([target]))
                return ok(f"Launched {target}")
            except Exception as e:
                return fail(f"Could not launch '{target}'", detail=str(e))

    if action == "type":
        import pyautogui

        await loop.run_in_executor(None, pyautogui.typewrite, detail, 0.02)
        return ok("Typed the requested text.")

    if action == "hotkey":
        import pyautogui

        keys = [k.strip() for k in detail.replace(",", "+").split("+") if k.strip()]
        if not keys:
            return fail("No keys provided.")
        await loop.run_in_executor(None, lambda: pyautogui.hotkey(*keys))
        return ok(f"Pressed {'+'.join(keys)}")

    if action == "click":
        import pyautogui

        nums = re.findall(r"-?\d+", detail)
        if len(nums) < 2:
            return fail("Click needs x,y coordinates.")
        x, y = int(nums[0]), int(nums[1])
        await loop.run_in_executor(None, pyautogui.click, x, y)
        return ok(f"Clicked at {x},{y}")

    if action == "click_text":
        # Vision-guided fallback: OCR-locate the text and click it, so
        # "click the Save button" works on arbitrary apps, not just the
        # handful of commands with dedicated tools.
        from Tools.click_on_text import click_on_screen_text

        result = await click_on_screen_text(command=detail)
        return result

    return fail(f"Unknown action '{action}'.")

