"""
Shared structured result contract for all Tony tools.

Per the reliability workstream, every tool should return a consistent
result shape so the router and the LLM tool-calling layer can distinguish
"tool failed, retry", "tool succeeded with a warning", and "tool refused
(safety block)" instead of parsing ad hoc strings.

Tool functions exposed to the LLM (`@function_tool()`) still return a
plain string (required by the function-calling schema), but that string
is produced by `format_result()` below so the shape is consistent and
machine-parseable by `execute_tool()` in core/runtime_agent.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ToolResult:
    ok: bool
    message: str
    detail: Optional[str] = None

    def to_string(self) -> str:
        """Human/LLM-facing string. Keeps backward compatibility with tools
        that have always returned plain strings, while embedding a machine
        parseable JSON tag that execute_tool() can detect and unwrap."""
        prefix = "✅" if self.ok else "❌"
        text = f"{prefix} {self.message}"
        if self.detail:
            text += f" ({self.detail})"
        return text

    def to_dict(self) -> dict:
        return asdict(self)


def ok(message: str, detail: Optional[str] = None) -> str:
    return ToolResult(True, message, detail).to_string()


def fail(message: str, detail: Optional[str] = None) -> str:
    return ToolResult(False, message, detail).to_string()


def is_failure(result_text: str) -> bool:
    """Best-effort detection of a failure result from a tool's returned string."""
    if not isinstance(result_text, str):
        return False
    stripped = result_text.strip()
    return stripped.startswith("❌") or stripped.lower().startswith("error")
