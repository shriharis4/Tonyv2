"""
Minimal conversation memory database for Tony assistant.

Stores and retrieves conversation history for context awareness.
Restored to fix regression where history loading failed silently.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, NamedTuple


class ConversationRecord(NamedTuple):
    """Single conversation turn (user or assistant message)"""
    role: str  # "user" or "assistant"
    content: str  # The message text
    timestamp: str  # ISO format datetime


class MemoryDatabase:
    """SQLite-backed conversation history storage"""

    def __init__(self, db_path: str = "tony_memory.db"):
        """Initialize or connect to the conversation database"""
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self):
        """Create tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"[MEMORY_DB] Schema creation error: {e}")

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
