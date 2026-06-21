"""
SQLite 資料庫模組 — 行程 + 待辦事項
每個群組（group_id）有自己獨立的資料空間
"""

import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "bot_data.db")


class Database:
    def __init__(self):
        self._init_tables()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_tables(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    datetime TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    completed_at TEXT
                )
            """)

    # ── 行程 ────────────────────────────────────────────
    def add_event(self, group_id: str, user_id: str, title: str, dt_str: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO events (group_id, user_id, title, datetime) VALUES (?, ?, ?, ?)",
                (group_id, user_id, title, dt_str),
            )

    def get_upcoming_events(self, group_id: str, days: int = 7) -> list:
        """取得未來 N 天的行程（依時間排序）"""
        today = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE group_id = ? AND datetime >= ? AND datetime < ? ORDER BY datetime ASC",
                (group_id, today, end_date),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_event_by_keyword(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE group_id = ? AND title LIKE ? LIMIT 1",
                (group_id, f"%{keyword}%"),
            ).fetchone()
            if row:
                conn.execute("DELETE FROM events WHERE id = ?", (row["id"],))
                return dict(row)
        return None

    # ── 待辦 ────────────────────────────────────────────
    def add_todo(self, group_id: str, user_id: str, title: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO todos (group_id, user_id, title) VALUES (?, ?, ?)",
                (group_id, user_id, title),
            )

    def get_todos(self, group_id: str, status: str = "pending") -> list:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM todos WHERE group_id = ? AND status = ? ORDER BY created_at ASC",
                (group_id, status),
            ).fetchall()
        return [dict(r) for r in rows]

    def complete_todo_by_keyword(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM todos WHERE group_id = ? AND status = 'pending' AND title LIKE ? LIMIT 1",
                (group_id, f"%{keyword}%"),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE todos SET status = 'completed', completed_at = datetime('now', 'localtime') WHERE id = ?",
                    (row["id"],),
                )
                return dict(row)
        return None

    def delete_todo_by_keyword(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM todos WHERE group_id = ? AND status = 'pending' AND title LIKE ? LIMIT 1",
                (group_id, f"%{keyword}%"),
            ).fetchone()
            if row:
                conn.execute("DELETE FROM todos WHERE id = ?", (row["id"],))
                return dict(row)
        return None
