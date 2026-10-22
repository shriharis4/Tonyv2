"""
Tests for tool_registry.py (single source of truth for tool registration)
and Tools/tool_result.py (structured result contract).
"""

import tool_registry
import tools as tools_facade
from Tools.tool_result import ok, fail, is_failure


def test_tools_facade_and_registry_export_identical_callables():
    """Both tools.py and tool_registry.py must expose the exact same
    function objects for every tool — this is the dedup guarantee from
    Workstream 2 item 2: a tool can never exist in one path but not the
    other."""
    shared_names = [
        "manage_window", "search_web", "open_app", "system_power_action",
        "write_document", "edit_existing_file", "send_email",
        "browser_automate", "delete_file_or_folder",
    ]
    for name in shared_names:
        assert hasattr(tool_registry, name), f"{name} missing from tool_registry"
        assert hasattr(tools_facade, name), f"{name} missing from tools.py facade"
        assert getattr(tool_registry, name) is getattr(tools_facade, name), (
            f"{name} is a different object in tools.py vs tool_registry.py — "
            "dedup guarantee broken"
        )


def test_get_all_tool_functions_returns_callables():
    funcs = tool_registry.get_all_tool_functions()
    assert len(funcs) > 50
    assert all(callable(f) for f in funcs)


def test_no_duplicate_names_in_full_tool_list():
    funcs = tool_registry.get_all_tool_functions()
    names = [getattr(f, "__name__", None) for f in funcs]
    assert len(names) == len(set(names)), "Duplicate tool name registered twice"


def test_ok_result_contract():
    result = ok("Document created", detail="format=word")
    assert result.startswith("✅")
    assert "Document created" in result
    assert "format=word" in result
    assert is_failure(result) is False


def test_fail_result_contract():
    result = fail("Could not find file", detail="not_found")
    assert result.startswith("❌")
    assert "Could not find file" in result
    assert is_failure(result) is True


def test_is_failure_handles_non_string_gracefully():
    assert is_failure(None) is False
    assert is_failure(123) is False
    assert is_failure("") is False
