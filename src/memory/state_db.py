import sqlite3
import os
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional
from config.settings import BASE_DIR

DEFAULT_DB_PATH = BASE_DIR / ".agent_state.db"

class StateDatabase:
    """
    SQLite backing store for session state, task DAGs, project memory, and execution history.
    Provides ACID guarantees and thread-safe persistence.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self._init_schema()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                goal TEXT NOT NULL,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                dependencies TEXT, -- JSON array of task IDs
                assigned_to TEXT,  -- model or worker name
                status TEXT NOT NULL, -- PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
                inputs TEXT,       -- JSON dict
                outputs TEXT,      -- JSON dict
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, id),
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS project_memory (
                key TEXT PRIMARY KEY,
                category TEXT NOT NULL, -- architecture, convention, decision, file_summary
                content TEXT NOT NULL,
                file_path TEXT,
                file_hash TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                task_id TEXT,
                tool_name TEXT NOT NULL,
                tool_input TEXT NOT NULL,
                tool_output TEXT,
                status TEXT NOT NULL, -- SUCCESS, ERROR
                execution_time_ms REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
            CREATE INDEX IF NOT EXISTS idx_exec_session ON execution_history(session_id);
            CREATE INDEX IF NOT EXISTS idx_exec_task ON execution_history(task_id);
            """)

    # --- Session Operations ---
    def create_session(self, session_id: str, goal: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO sessions (id, status, goal, metadata) VALUES (?, ?, ?, ?)",
                (session_id, "ACTIVE", goal, json.dumps(metadata or {}))
            )

    def update_session_status(self, session_id: str, status: str) -> None:
        with self._connection() as conn:
            conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["metadata"] = json.loads(res["metadata"]) if res["metadata"] else {}
            return res

    # --- Task Operations ---
    def add_task(
        self,
        task_id: str,
        session_id: str,
        title: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        assigned_to: str = "unassigned",
        status: str = "PENDING",
        inputs: Optional[Dict[str, Any]] = None
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO tasks (id, session_id, title, description, dependencies, assigned_to, status, inputs)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, session_id, title, description, json.dumps(dependencies or []), assigned_to, status, json.dumps(inputs or {}))
            )

    def update_task_status(
        self,
        task_id: str,
        status: str,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        with self._connection() as conn:
            if session_id:
                conn.execute(
                    """UPDATE tasks
                       SET status = ?, outputs = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ? AND session_id = ?""",
                    (status, json.dumps(outputs or {}), error, task_id, session_id)
                )
            else:
                conn.execute(
                    """UPDATE tasks
                       SET status = ?, outputs = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (status, json.dumps(outputs or {}), error, task_id)
                )

    def get_tasks_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM tasks WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["dependencies"] = json.loads(item["dependencies"]) if item["dependencies"] else []
                item["inputs"] = json.loads(item["inputs"]) if item["inputs"] else {}
                item["outputs"] = json.loads(item["outputs"]) if item["outputs"] else {}
                results.append(item)
            return results

    # --- Project Memory Operations ---
    def set_memory(self, key: str, category: str, content: str, file_path: Optional[str] = None, file_hash: Optional[str] = None) -> None:
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO project_memory (key, category, content, file_path, file_hash, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET
                       category = excluded.category,
                       content = excluded.content,
                       file_path = excluded.file_path,
                       file_hash = excluded.file_hash,
                       updated_at = CURRENT_TIMESTAMP""",
                (key, category, content, file_path, file_hash)
            )

    def get_memory(self, key: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM project_memory WHERE key = ?", (key,)).fetchone()
            return dict(row) if row else None

    def get_memories_by_category(self, category: str) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM project_memory WHERE category = ?", (category,)).fetchall()
            return [dict(r) for r in rows]

    # --- Execution History Operations ---
    def log_tool_execution(
        self,
        session_id: str,
        task_id: Optional[str],
        tool_name: str,
        tool_input: Any,
        tool_output: Any,
        status: str,
        execution_time_ms: float
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO execution_history (session_id, task_id, tool_name, tool_input, tool_output, status, execution_time_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    task_id,
                    tool_name,
                    json.dumps(tool_input) if not isinstance(tool_input, str) else tool_input,
                    json.dumps(tool_output) if not isinstance(tool_output, str) else tool_output,
                    status,
                    execution_time_ms
                )
            )

    def get_recent_history(self, session_id: str, limit: int = 15) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT * FROM execution_history
                   WHERE session_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (session_id, limit)
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    # --- Agent Messages ---
    def log_message(self, session_id: str, sender: str, receiver: str, message_type: str, content: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO agent_messages (session_id, sender, receiver, message_type, content)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, sender, receiver, message_type, content)
            )

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM agent_messages WHERE session_id = ? ORDER BY id ASC", (session_id,)).fetchall()
            return [dict(r) for r in rows]
