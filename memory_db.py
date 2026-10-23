"""
Minimal conversation memory database for Tony assistant.

Stores and retrieves conversation history for context awareness.
Restored to fix regression where history loading failed silently.

Schema versioning: the `schema_version` table tracks the current schema
version so future migrations can detect and upgrade older databases
instead of silently failing or losing data. If the database file is
corrupt (fails to open as SQLite), `MemoryDatabase` backs up the corrupt
file and starts a fresh one rather than crashing the app on launch.
"""

import logging
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Optional, NamedTuple

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 2


class ConversationRecord(NamedTuple):
    """Single conversation turn (user or assistant message)"""
    role: str  # "user" or "assistant"
    content: str  # The message text
    timestamp: str  # ISO format datetime


def _create_tables(conn):
    """Create all tables if they don't exist. Shared by the normal and
    corruption-recovery schema paths so the DDL lives in exactly one place."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    # Per-turn latency log (TurnTimer t0-t10 breakdown) for offline
    # latency/regression analysis — the spec's Workstream 1 item 1.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS turn_timings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            command TEXT,
            route TEXT,
            total_latency REAL,
            speech_to_transcript REAL,
            transcript_to_router REAL,
            router_to_tool REAL,
            tool_duration REAL,
            tts_duration REAL
        )
    """)


class MemoryDatabase:
    """SQLite-backed conversation history storage"""

    def __init__(self, db_path: str = "tony_memory.db",
                 perf_db_path: str = None):
        """Initialize or connect to the conversation database.

        `db_path` holds the `conversations` table and may be a per-SESSION
        file that is deleted on clean shutdown (see runtime_agent's
        session-DB wiring). `perf_db_path` holds the `turn_timings` table
        and is intentionally a SEPARATE, PERSISTENT file that is never
        deleted — it is the latency-diagnosis history that made the whole
        investigation possible, so it must survive across sessions even
        when conversation history is wiped. The two concerns (chat-history
        privacy/size vs. perf instrumentation) happen to have historically
        shared one file; this keeps them apart.

        When `perf_db_path` is not given, it defaults to
        `tony_perf_history.db` placed in the SAME directory as `db_path`.
        This keeps the perf history as a stable sibling of the (possibly
        per-session) conversations DB in production, while test suites that
        point `db_path` at a tmp dir automatically get an isolated perf file
        in that same tmp dir rather than polluting a shared one.
        """
        self.db_path = Path(db_path)
        if perf_db_path is None:
            self.perf_db_path = self.db_path.parent / "tony_perf_history.db"
        else:
            self.perf_db_path = Path(perf_db_path)
        self._ensure_schema()
        self._ensure_perf_schema()

    def _ensure_perf_schema(self):
        """Create the turn_timings table in the persistent perf DB. Separate
        from _ensure_schema so a per-session conversations DB and the
        persistent perf DB can live in different files. Best-effort."""
        try:
            conn = sqlite3.connect(self.perf_db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS turn_timings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        command TEXT,
                        route TEXT,
                        total_latency REAL,
                        speech_to_transcript REAL,
                        transcript_to_router REAL,
                        router_to_tool REAL,
                        tool_duration REAL,
                        tts_duration REAL
                    )
                """)
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"[MEMORY_DB] perf schema init failed: {e}")

    def _recover_corrupt_db(self):
        """If the DB file exists but isn't a valid SQLite database, back it
        up with a timestamp suffix and start fresh instead of crashing."""
        if not self.db_path.exists():
            return
        backup_path = self.db_path.with_suffix(
            f".corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
        )
        try:
            shutil.move(str(self.db_path), str(backup_path))
            logger.warning(
                f"[MEMORY_DB] Corrupt database detected. Backed up to {backup_path} "
                "and starting a fresh conversation store."
            )
        except Exception as e:
            logger.error(f"[MEMORY_DB] Failed to back up corrupt database: {e}")

    def _ensure_schema(self):
        """Create tables if they don't exist. Detects corruption and schema
        version, recovering/migrating as needed."""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                # Will raise sqlite3.DatabaseError if the file exists but
                # isn't a valid SQLite database (corruption).
                conn.execute("PRAGMA integrity_check")

                _create_tables(conn)

                row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO schema_version (version) VALUES (?)",
                        (CURRENT_SCHEMA_VERSION,),
                    )
                elif row[0] < CURRENT_SCHEMA_VERSION:
                    # Future migrations would run here based on row[0].
                    # (CREATE TABLE IF NOT EXISTS above already adds any new
                    # tables for the bump to v2; bump the stored version.)
                    conn.execute(
                        "UPDATE schema_version SET version = ?",
                        (CURRENT_SCHEMA_VERSION,),
                    )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.DatabaseError as e:
            logger.error(f"[MEMORY_DB] Database corruption detected: {e}")
            try:
                self._recover_corrupt_db()
                # Retry once on a fresh file.
                conn = sqlite3.connect(self.db_path)
                try:
                    _create_tables(conn)
                    conn.execute(
                        "INSERT INTO schema_version (version) VALUES (?)",
                        (CURRENT_SCHEMA_VERSION,),
                    )
                    conn.commit()
                finally:
                    conn.close()
            except Exception as recovery_err:
                # If recovery itself fails (e.g. the corrupt file couldn't be
                # moved aside due to a file lock/permissions), do NOT let the
                # exception escape MemoryDatabase.__init__ and crash app
                # startup. Memory/history will be unavailable this session,
                # which is a graceful degradation, not a crash.
                logger.error(f"[MEMORY_DB] Recovery failed; running without persistent memory this session: {recovery_err}")
        except Exception as e:
            logger.error(f"[MEMORY_DB] Schema creation error: {e}")

    def add_message(self, role: str, content: str) -> bool:
        """Add a message to conversation history"""
        if not content or not content.strip():
            return False

        try:
            timestamp = datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
                    (role, content.strip(), timestamp)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"[MEMORY_DB] Add message error: {e}")
            return False

    def get_conversation_history(self, limit: int = 20) -> List[ConversationRecord]:
        """Retrieve recent conversation history (newest first)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT role, content, timestamp
                    FROM conversations
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
                records = [
                    ConversationRecord(
                        role=row["role"],
                        content=row["content"],
                        timestamp=row["timestamp"]
                    )
                    for row in cursor.fetchall()
                ]
            return records
        except Exception as e:
            print(f"[MEMORY_DB] Get history error: {e}")
            return []

    def clear_history(self) -> bool:
        """Clear all conversation history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM conversations")
                conn.commit()
            return True
        except Exception as e:
            print(f"[MEMORY_DB] Clear history error: {e}")
            return False

    def get_last_n_messages(self, n: int = 10) -> List[ConversationRecord]:
        """Get the last N messages in chronological order"""
        try:
            history = self.get_conversation_history(limit=n)
            return list(reversed(history))  # Reverse to chronological
        except Exception as e:
            print(f"[MEMORY_DB] Get last n error: {e}")
            return []

    def log_turn_timing(
        self,
        command: str,
        route: str,
        total_latency: float,
        speech_to_transcript: Optional[float] = None,
        transcript_to_router: Optional[float] = None,
        router_to_tool: Optional[float] = None,
        tool_duration: Optional[float] = None,
        tts_duration: Optional[float] = None,
    ) -> bool:
        """Persist one turn's latency breakdown (from TurnTimer t0-t10) so
        regressions are visible in data, not guessed at. Best-effort: never
        raises into the turn pipeline."""
        try:
            with sqlite3.connect(self.perf_db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO turn_timings (
                        timestamp, command, route, total_latency,
                        speech_to_transcript, transcript_to_router,
                        router_to_tool, tool_duration, tts_duration
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now().isoformat(),
                        (command or "")[:500],
                        route,
                        total_latency,
                        speech_to_transcript,
                        transcript_to_router,
                        router_to_tool,
                        tool_duration,
                        tts_duration,
                    ),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.warning(f"[MEMORY_DB] log_turn_timing failed: {e}")
            return False

    def get_recent_timings(self, limit: int = 50) -> List[dict]:
        """Return the most recent turn-timing rows (newest first) for
        offline latency analysis / computing p50/p95."""
        try:
            with sqlite3.connect(self.perf_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM turn_timings ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"[MEMORY_DB] get_recent_timings failed: {e}")
            return []
