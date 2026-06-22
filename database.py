"""
PostgreSQL 資料庫模組 — 行程 + 待辦事項 + 購物清單
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
                    recurrence TEXT DEFAULT '',
                    archived BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # 安全地為既有資料表加欄位
            for col, definition in [
                ("recurrence", "TEXT DEFAULT ''"),
                ("archived", "BOOLEAN DEFAULT FALSE"),
            ]:
                cur.execute(f"""
                    DO $$ BEGIN
                        ALTER TABLE events ADD COLUMN {col} {definition};
                    EXCEPTION WHEN duplicate_column THEN NULL;
                    END $$;
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS shopping_list (
                    id SERIAL PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    item TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """)

    # ── 行程 ────────────────────────────────────────────
    def add_event(self, group_id: str, user_id: str, title: str, dt_str: str,
                  recurrence: str = ""):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO events (group_id, user_id, title, datetime, recurrence) VALUES (%s, %s, %s, %s, %s)",
                (group_id, user_id, title, dt_str, recurrence),
            )

    def get_upcoming_events(self, group_id: str, days: int = 7) -> list:
        """取得未來 N 天的行程（依時間排序，排除已歸檔），至少查 1 天"""
        today = now_tw().strftime("%Y-%m-%d")
        end_date = (now_tw() + timedelta(days=max(days, 1))).strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND archived = FALSE AND datetime >= %s AND datetime < %s ORDER BY datetime ASC",
                (group_id, today, end_date),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_all_events(self, group_id: str) -> list:
        """取得所有未歸檔行程"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND archived = FALSE ORDER BY datetime ASC",
                (group_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def search_events(self, group_id: str, keyword: str) -> list:
        """依關鍵字搜尋所有行程（含已歸檔的，用於歷史查詢）"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND title LIKE %s ORDER BY datetime DESC",
                (group_id, f"%{keyword}%"),
            )
            return [dict(r) for r in cur.fetchall()]

    def delete_event_by_keyword(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND archived = FALSE AND title LIKE %s LIMIT 1",
                (group_id, f"%{keyword}%"),
            )
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM events WHERE id = %s", (row["id"],))
                return dict(row)
        return None

    def archive_old_events(self, days_old: int = 365):
        """將超過指定天數的過期行程歸檔"""
        cutoff = (now_tw() - timedelta(days=days_old)).strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE events SET archived = TRUE WHERE archived = FALSE AND datetime < %s",
                (cutoff,),
            )
            return cur.rowcount

    def get_recurring_events(self, group_id: str) -> list:
        """取得所有週期性行程"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND recurrence != '' AND archived = FALSE ORDER BY datetime ASC",
                (group_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_all_group_ids(self) -> list:
        """取得所有有資料的 group_id（用於排程推播）"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT group_id FROM events UNION SELECT DISTINCT group_id FROM todos UNION SELECT DISTINCT group_id FROM shopping_list")
            return [row[0] for row in cur.fetchall()]

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

    # ── 購物清單 ────────────────────────────────────────
    def add_shopping_item(self, group_id: str, user_id: str, item: str):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO shopping_list (group_id, user_id, item) VALUES (%s, %s, %s)",
                (group_id, user_id, item),
            )

    def get_shopping_list(self, group_id: str, status: str = "pending") -> list:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM shopping_list WHERE group_id = %s AND status = %s ORDER BY created_at ASC",
                (group_id, status),
            )
            return [dict(r) for r in cur.fetchall()]

    def complete_shopping_item(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM shopping_list WHERE group_id = %s AND status = 'pending' AND item LIKE %s LIMIT 1",
                (group_id, f"%{keyword}%"),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE shopping_list SET status = 'bought', completed_at = NOW() WHERE id = %s",
                    (row["id"],),
                )
                return dict(row)
        return None

    def delete_shopping_item(self, group_id: str, keyword: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM shopping_list WHERE group_id = %s AND status = 'pending' AND item LIKE %s LIMIT 1",
                (group_id, f"%{keyword}%"),
            )
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM shopping_list WHERE id = %s", (row["id"],))
                return dict(row)
        return None

    def clear_bought_items(self, group_id: str) -> int:
        """清除所有已購買的項目"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM shopping_list WHERE group_id = %s AND status = 'bought'",
                (group_id,),
            )
            return cur.rowcount
