"""General desktop fallback when a request does not match a dedicated Tools/ module."""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
import webbrowser
from typing import Literal

from livekit.agents import function_tool

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
    action: Literal["launch", "type", "hotkey", "click", "open_url", "open_path"],
    detail: str,
) -> str:
    """
    Carry out a reasonable desktop action that has no dedicated tool.

    Safety: refuses destructive file deletion, disk format, and system power
    commands. Use system_power_action for shutdown/restart/lock/sleep.
    """
    detail = (detail or "").strip()
    if not detail:
        return "Need a concrete action detail."
    if _blocked(detail):
        return (
            "Blocked: destructive or power operations must use the dedicated "
            "system_power_action tool after the existing confirmation pattern."
        )

    loop = asyncio.get_running_loop()

    if action == "open_url":
        url = detail if re.match(r"^https?://", detail, re.I) else f"https://{detail}"
        await loop.run_in_executor(None, webbrowser.open, url)
        return f"Opened {url}"

    if action == "open_path":
        path = os.path.expandvars(os.path.expanduser(detail))
        if not os.path.exists(path):
            return f"Path not found: {path}"
        await loop.run_in_executor(None, os.startfile, path)
        return f"Opened {path}"

    if action == "launch":
        await loop.run_in_executor(
            None, lambda: subprocess.Popen(f'start "" {detail}', shell=True)
        )
        return f"Launched {detail}"

    if action == "type":
        import pyautogui

        await loop.run_in_executor(None, pyautogui.typewrite, detail, 0.02)
        return "Typed the requested text."

    if action == "hotkey":
        import pyautogui

        keys = [k.strip() for k in detail.replace(",", "+").split("+") if k.strip()]
        if not keys:
            return "No keys provided."
        await loop.run_in_executor(None, lambda: pyautogui.hotkey(*keys))
        return f"Pressed {'+'.join(keys)}"

    if action == "click":
        import pyautogui

        nums = re.findall(r"-?\d+", detail)
        if len(nums) < 2:
            return "Click needs x,y coordinates."
        x, y = int(nums[0]), int(nums[1])
        await loop.run_in_executor(None, pyautogui.click, x, y)
        return f"Clicked at {x},{y}"

    return f"Unknown action '{action}'."
