"""
Tests for the SQLite per-turn timing log (memory_db.turn_timings table).
"""

from memory_db import MemoryDatabase, CURRENT_SCHEMA_VERSION


def test_schema_version_is_current(tmp_path):
    import sqlite3
    db_path = tmp_path / "t.db"
    MemoryDatabase(str(db_path))
    ver = sqlite3.connect(str(db_path)).execute("SELECT version FROM schema_version").fetchone()[0]
    assert ver == CURRENT_SCHEMA_VERSION


def test_log_and_read_turn_timing(tmp_path):
    db = MemoryDatabase(str(tmp_path / "t.db"))

    assert db.log_turn_timing(
        command="open chrome", route="direct", total_latency=0.85,
        transcript_to_router=0.01, router_to_tool=0.4, tool_duration=0.3,
        tts_duration=0.1,
    ) is True
    assert db.log_turn_timing(command="tell me a joke", route="llm", total_latency=1.6) is True

    rows = db.get_recent_timings(10)
    assert len(rows) == 2
    # Newest first
    assert rows[0]["command"] == "tell me a joke"
    assert rows[0]["route"] == "llm"
    assert rows[1]["command"] == "open chrome"
    assert rows[1]["total_latency"] == 0.85


def test_turn_timings_table_coexists_with_conversations(tmp_path):
    db = MemoryDatabase(str(tmp_path / "t.db"))
    db.add_message("user", "hello")
    db.log_turn_timing(command="hello", route="direct", total_latency=0.2)
    assert len(db.get_conversation_history()) == 1
    assert len(db.get_recent_timings()) == 1
