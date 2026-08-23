"""
SQLite-backed trace store.

Append-only by design: sessions write events as they happen, nothing
gets edited after the fact. This is what makes the audit trail
"deterministic" - it's a record of what occurred, not a summary
generated afterward.
"""

import sqlite3
from pathlib import Path
from typing import List
from storage.schema import TraceEvent

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trace_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    action TEXT NOT NULL,
    file TEXT,
    reasoning TEXT,
    diff TEXT,
    test_result TEXT,
    test_output TEXT,
    tests_passed INTEGER,
    tests_failed INTEGER,
    failing_tests TEXT,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_session ON trace_events(session_id);
CREATE INDEX IF NOT EXISTS idx_session_step ON trace_events(session_id, step);
"""


class TraceStore:
    def __init__(self, db_path: str = "traces/traces.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def log(self, event: TraceEvent) -> int:
        cur = self._conn.execute(
            """INSERT INTO trace_events
               (session_id, step, action, file, reasoning, diff,
                test_result, test_output, tests_passed, tests_failed,
                failing_tests, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.session_id, event.step, event.action, event.file,
                event.reasoning, event.diff, event.test_result,
                event.test_output, event.tests_passed, event.tests_failed,
                event.failing_tests, event.timestamp,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_session(self, session_id: str) -> List[dict]:
        cur = self._conn.execute(
            "SELECT * FROM trace_events WHERE session_id = ? ORDER BY step ASC",
            (session_id,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def list_sessions(self) -> List[str]:
        cur = self._conn.execute(
            """SELECT session_id, MIN(timestamp) as start
               FROM trace_events GROUP BY session_id ORDER BY start DESC"""
        )
        return [row[0] for row in cur.fetchall()]

    def close(self):
        self._conn.close()