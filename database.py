"""
PostgreSQL 資料庫模組 — 行程 + 待辦事項
每個群組（group_id）有自己獨立的資料空間
使用 Railway 提供的 DATABASE_URL 連線
"""

import os
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# 台灣時區 UTC+8
TW = timezone(timedelta(hours=8))


def now_tw():
    """取得台灣時間"""
    return datetime.now(TW)


class Database:
    def __init__(self):
        self._init_tables()

    @contextmanager
    def _get_conn(self):
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    datetime TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """)

    # ── 行程 ────────────────────────────────────────────
    def add_event(self, group_id: str, user_id: str, title: str, dt_str: str):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO events (group_id, user_id, title, datetime) VALUES (%s, %s, %s, %s)",
                (group_id, user_id, title, dt_str),
            )

    def get_upcoming_events(self, group_id: str, days: int = 7) -> list:
        """取得未來 N 天的行程（依時間排序），至少查 1 天"""
        today = now_tw().strftime("%Y-%m-%d")
        end_date = (now_tw() + timedelta(days=max(days, 1))).strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND datetime >= %s AND datetime < %s ORDER BY datetime ASC",
                (group_id, today, end_date),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_all_events(self, group_id: str) -> list:
        """取得所有行程（不過濾日期）"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s ORDER BY datetime ASC",
                (group_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def delete_event_by_keyword(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND title LIKE %s LIMIT 1",
                (group_id, f"%{keyword}%"),
            )
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM events WHERE id = %s", (row["id"],))
                return dict(row)
        return None

    # ── 待辦 ────────────────────────────────────────────
    def add_todo(self, group_id: str, user_id: str, title: str):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO todos (group_id, user_id, title) VALUES (%s, %s, %s)",
                (group_id, user_id, title),
            )

    def get_todos(self, group_id: str, status: str = "pending") -> list:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM todos WHERE group_id = %s AND status = %s ORDER BY created_at ASC",
                (group_id, status),
            )
            return [dict(r) for r in cur.fetchall()]

    def complete_todo_by_keyword(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM todos WHERE group_id = %s AND status = 'pending' AND title LIKE %s LIMIT 1",
                (group_id, f"%{keyword}%"),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE todos SET status = 'completed', completed_at = NOW() WHERE id = %s",
                    (row["id"],),
                )
                return dict(row)
        return None

    def delete_todo_by_keyword(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM todos WHERE group_id = %s AND status = 'pending' AND title LIKE %s LIMIT 1",
                (group_id, f"%{keyword}%"),
            )
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM todos WHERE id = %s", (row["id"],))
                return dict(row)
        return None
