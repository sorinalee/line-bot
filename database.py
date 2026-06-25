"""
PostgreSQL 資料庫模組 — 行程 + 待辦事項 + 購物清單 + 生日
每個群組（group_id）有自己獨立的資料空間
使用 Railway 提供的 DATABASE_URL 連線
"""

import os
from datetime import datetime, timedelta, timezone, date
from contextlib import contextmanager
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras
from lunardate import LunarDate

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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS birthdays (
                    id SERIAL PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    month INTEGER NOT NULL,
                    day INTEGER NOT NULL,
                    year INTEGER,
                    is_lunar BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                DO $$ BEGIN
                    ALTER TABLE birthdays ADD COLUMN is_lunar BOOLEAN DEFAULT FALSE;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
            cur.execute("""
                DO $$ BEGIN
                    ALTER TABLE birthdays ADD COLUMN event_type TEXT DEFAULT 'birthday';
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS collections (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '未分類',
                    title TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    raw_text TEXT NOT NULL DEFAULT '',
                    source_url TEXT DEFAULT '',
                    status TEXT DEFAULT 'unread',
                    image_data BYTEA,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                DO $$ BEGIN
                    ALTER TABLE collections ADD COLUMN image_data BYTEA;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
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

    def get_events_by_date(self, group_id: str, date_str: str) -> list:
        """取得特定日期的行程"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND archived = FALSE AND datetime LIKE %s ORDER BY datetime ASC",
                (group_id, f"{date_str}%"),
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

    def delete_event_by_keyword(self, group_id: str, keyword: str) -> list:
        """刪除所有匹配關鍵字的未歸檔行程，回傳被刪除的行程列表"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND archived = FALSE AND title LIKE %s ORDER BY datetime",
                (group_id, f"%{keyword}%"),
            )
            rows = [dict(r) for r in cur.fetchall()]
            if rows:
                ids = [r["id"] for r in rows]
                cur.execute("DELETE FROM events WHERE id = ANY(%s)", (ids,))
            return rows

    def update_event_by_keyword(self, group_id: str, keyword: str,
                                new_date: str = "", new_time: str = "",
                                new_title: str = "") -> dict | None:
        """依關鍵字找到行程並更新日期/時間/標題，回傳更新後的行程"""
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM events WHERE group_id = %s AND archived = FALSE AND title LIKE %s ORDER BY datetime LIMIT 1",
                (group_id, f"%{keyword}%"),
            )
            row = cur.fetchone()
            if not row:
                return None
            row = dict(row)

            old_dt = row["datetime"]
            old_date_part = old_dt[:10] if len(old_dt) >= 10 else old_dt
            old_time_part = old_dt[11:] if len(old_dt) > 10 else ""

            updated_date = new_date if new_date else old_date_part
            updated_time = new_time if new_time else old_time_part
            updated_dt = f"{updated_date} {updated_time}".strip()
            updated_title = new_title if new_title else row["title"]

            cur.execute(
                "UPDATE events SET title = %s, datetime = %s WHERE id = %s",
                (updated_title, updated_dt, row["id"]),
            )
            row["title"] = updated_title
            row["datetime"] = updated_dt
            return row

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
            cur.execute("SELECT DISTINCT group_id FROM events UNION SELECT DISTINCT group_id FROM todos UNION SELECT DISTINCT group_id FROM shopping_list UNION SELECT DISTINCT group_id FROM birthdays")
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

    def complete_all_shopping(self, group_id: str) -> int:
        """將所有 pending 項目標記為 bought 並刪除"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM shopping_list WHERE group_id = %s AND status = 'pending'",
                (group_id,),
            )
            return cur.rowcount

    def clear_bought_items(self, group_id: str) -> int:
        """清除所有已購買的項目"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM shopping_list WHERE group_id = %s AND status = 'bought'",
                (group_id,),
            )
            return cur.rowcount

    # ── 生日 ────────────────────────────────────────────
    def add_birthday(self, group_id: str, name: str, month: int, day: int,
                     year: int | None = None, is_lunar: bool = False,
                     event_type: str = "birthday"):
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO birthdays (group_id, name, month, day, year, is_lunar, event_type) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (group_id, name, month, day, year, is_lunar, event_type),
            )

    def get_birthdays(self, group_id: str) -> list:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM birthdays WHERE group_id = %s ORDER BY month, day",
                (group_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def _lunar_to_solar(lunar_month: int, lunar_day: int, solar_year: int) -> date | None:
        """將農曆月日轉換為指定國曆年份對應的國曆日期"""
        try:
            ld = LunarDate(solar_year, lunar_month, lunar_day)
            return ld.toSolarDate()
        except ValueError:
            # 該年農曆沒有這一天（例如閏月差異），嘗試前一天
            try:
                ld = LunarDate(solar_year, lunar_month, lunar_day - 1)
                return ld.toSolarDate()
            except ValueError:
                return None

    def _get_solar_date_for_birthday(self, b: dict, target_year: int) -> date | None:
        """取得某筆生日在 target_year 對應的國曆日期"""
        if b.get("is_lunar"):
            return self._lunar_to_solar(b["month"], b["day"], target_year)
        else:
            try:
                return date(target_year, b["month"], b["day"])
            except ValueError:
                return None

    def get_todays_birthdays(self, group_id: str) -> list:
        """取得今天生日的人（支援農曆）"""
        now = now_tw()
        today = now.date()
        results = []
        all_bdays = self.get_birthdays(group_id)
        for b in all_bdays:
            solar = self._get_solar_date_for_birthday(b, now.year)
            if solar and solar == today:
                results.append(b)
        return results

    def get_upcoming_birthdays(self, group_id: str, days: int = 30) -> list:
        """取得未來 N 天內的生日（支援農曆）"""
        now = now_tw()
        today = now.date()
        results = []
        all_bdays = self.get_birthdays(group_id)
        for b in all_bdays:
            # 先查今年
            solar = self._get_solar_date_for_birthday(b, now.year)
            if solar and solar < today:
                # 今年已過，查明年
                solar = self._get_solar_date_for_birthday(b, now.year + 1)
            if solar is None:
                continue
            diff = (solar - today).days
            if 0 <= diff <= days:
                b = dict(b)
                b["days_until"] = diff
                b["solar_date"] = solar.strftime("%m/%d")
                if b.get("year"):
                    b["age"] = solar.year - b["year"]
                results.append(b)
        results.sort(key=lambda x: x["days_until"])
        return results

    def delete_birthday(self, group_id: str, name: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM birthdays WHERE group_id = %s AND name LIKE %s LIMIT 1",
                (group_id, f"%{name}%"),
            )
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM birthdays WHERE id = %s", (row["id"],))
                return dict(row)
        return None

    # ── 收藏 ────────────────────────────────────────────
    def add_collection(self, user_id: str, content_type: str, category: str,
                       title: str, summary: str, raw_text: str = "",
                       source_url: str = "") -> dict:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """INSERT INTO collections
                   (user_id, content_type, category, title, summary, raw_text, source_url)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (user_id, content_type, category, title, summary, raw_text, source_url),
            )
            return dict(cur.fetchone())

    def get_collections(self, user_id: str, category: str = "",
                        status: str = "") -> list:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            query = ("SELECT id, user_id, content_type, category, title, summary, "
                     "raw_text, source_url, status, created_at, "
                     "(image_data IS NOT NULL) AS has_image "
                     "FROM collections WHERE user_id = %s")
            params = [user_id]
            if category:
                query += " AND category = %s"
                params.append(category)
            if status:
                query += " AND status = %s"
                params.append(status)
            query += " ORDER BY created_at DESC"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def get_today_collections(self, user_id: str) -> list:
        today = now_tw().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id, user_id, content_type, category, title, summary, "
                "raw_text, source_url, status, created_at, "
                "(image_data IS NOT NULL) AS has_image "
                "FROM collections WHERE user_id = %s AND created_at::date = %s ORDER BY created_at DESC",
                (user_id, today),
            )
            return [dict(r) for r in cur.fetchall()]

    def search_collections(self, user_id: str, keywords: list) -> list:
        if not keywords:
            return []
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            conditions = []
            params = [user_id]
            for kw in keywords:
                conditions.append("(title LIKE %s OR summary LIKE %s OR raw_text LIKE %s)")
                params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
            where = " OR ".join(conditions)
            cur.execute(
                f"""SELECT id, user_id, content_type, category, title, summary,
                    raw_text, source_url, status, created_at,
                    (image_data IS NOT NULL) AS has_image
                    FROM collections
                    WHERE user_id = %s AND ({where})
                    ORDER BY created_at DESC LIMIT 20""",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def update_collection_memo(self, collection_id: int, title: str,
                               summary: str, category: str = "") -> None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            if category:
                cur.execute(
                    "UPDATE collections SET title = %s, summary = %s, raw_text = %s, category = %s WHERE id = %s",
                    (title, summary, summary, category, collection_id),
                )
            else:
                cur.execute(
                    "UPDATE collections SET title = %s, summary = %s, raw_text = %s WHERE id = %s",
                    (title, summary, summary, collection_id),
                )

    def get_all_user_ids_with_collections_today(self) -> list:
        today = now_tw().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT user_id FROM collections WHERE created_at::date = %s",
                (today,),
            )
            return [row[0] for row in cur.fetchall()]

    # ── 圖片暫存 ──────────────────────────────────────────

    def save_image_data(self, collection_id: int, image_bytes: bytes) -> None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE collections SET image_data = %s WHERE id = %s",
                (psycopg2.Binary(image_bytes), collection_id),
            )

    def clear_image_data(self, collection_id: int) -> None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE collections SET image_data = NULL WHERE id = %s",
                (collection_id,),
            )

    def get_pending_image_collections(self, user_id: str) -> list:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """SELECT id, title, summary, created_at FROM collections
                   WHERE user_id = %s AND image_data IS NOT NULL
                   ORDER BY created_at ASC""",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_image_data(self, collection_id: int) -> bytes | None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT image_data FROM collections WHERE id = %s",
                (collection_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return bytes(row[0])
            return None

    def get_image_storage_bytes(self) -> int:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(SUM(LENGTH(image_data)), 0) FROM collections WHERE image_data IS NOT NULL"
            )
            return cur.fetchone()[0]

    def delete_oldest_images(self, free_bytes: int) -> int:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, LENGTH(image_data) as size FROM collections
                   WHERE image_data IS NOT NULL ORDER BY created_at ASC"""
            )
            freed = 0
            deleted = 0
            for row in cur.fetchall():
                if freed >= free_bytes:
                    break
                cur.execute("UPDATE collections SET image_data = NULL WHERE id = %s", (row[0],))
                freed += row[1]
                deleted += 1
            return deleted

    def delete_collection(self, collection_id: int, user_id: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id, category, title FROM collections WHERE id = %s AND user_id = %s",
                (collection_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "DELETE FROM collections WHERE id = %s AND user_id = %s",
                (collection_id, user_id),
            )
            return dict(row)

    def delete_all_collections(self, user_id: str) -> int:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM collections WHERE user_id = %s RETURNING id",
                (user_id,),
            )
            return cur.rowcount

    def get_collection_by_id(self, collection_id: int, user_id: str) -> dict | None:
        with self._get_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM collections WHERE id = %s AND user_id = %s",
                (collection_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def update_collection_text(self, collection_id: int, raw_text: str,
                               title: str = "", summary: str = "") -> None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            fields = ["raw_text = %s"]
            params = [raw_text]
            if title:
                fields.append("title = %s")
                params.append(title)
            if summary:
                fields.append("summary = %s")
                params.append(summary)
            params.append(collection_id)
            cur.execute(
                f"UPDATE collections SET {', '.join(fields)} WHERE id = %s",
                params,
            )
