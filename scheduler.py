"""
排程模組 — APScheduler 每日推播 + 週期行程自動產生 + 行程歸檔
"""

import os
import re
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from database import Database
from weather_handler import get_weather

TW = timezone(timedelta(hours=8))


def now_tw():
    return datetime.now(TW)


def start_scheduler(app):
    """啟動所有排程任務"""
    scheduler = BackgroundScheduler(timezone="Asia/Taipei")
    scheduler.add_job(daily_morning_push, "cron", hour=7, minute=30)
    scheduler.add_job(daily_evening_summary, "cron", hour=21, minute=0)
    scheduler.add_job(generate_recurring_events, "cron", hour=0, minute=5)
    scheduler.add_job(archive_old_events_job, "cron", day_of_week="sun", hour=3)
    scheduler.start()


def push_message(group_id: str, text: str):
    """推播訊息到指定群組"""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        return
    configuration = Configuration(access_token=token)
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.push_message(
            PushMessageRequest(
                to=group_id,
                messages=[TextMessage(text=text)],
            )
        )


def daily_morning_push():
    """每天早上推播當日行程 + 天氣"""
    db = Database()
    group_ids = db.get_all_group_ids()

    for group_id in group_ids:
        today_events = db.get_upcoming_events(group_id, days=1)
        pending_todos = db.get_todos(group_id, status="pending")
        shopping = db.get_shopping_list(group_id, status="pending")

        today_str = now_tw().strftime("%m/%d（%A）")
        weekday_map = {
            "Monday": "一", "Tuesday": "二", "Wednesday": "三",
            "Thursday": "四", "Friday": "五", "Saturday": "六", "Sunday": "日",
        }
        for eng, chi in weekday_map.items():
            today_str = today_str.replace(eng, chi)

        lines = [f"☀️ 早安！今天是 {today_str}", ""]

        # 生日提醒
        todays_bdays = db.get_todays_birthdays(group_id)
        if todays_bdays:
            for b in todays_bdays:
                age_str = ""
                if b.get("year"):
                    age = now_tw().year - b["year"]
                    age_str = f"（{age} 歲）"
                lunar_tag = "🌙農曆 " if b.get("is_lunar") else ""
                lines.append(f"🎂 今天是 {b['name']} 的{lunar_tag}生日{age_str}！生日快樂！🎉")
            lines.append("")

        # 近期生日預告（未來7天內，排除今天）
        upcoming_bdays = db.get_upcoming_birthdays(group_id, days=7)
        upcoming_bdays = [b for b in upcoming_bdays if b["days_until"] > 0]
        if upcoming_bdays:
            for b in upcoming_bdays:
                lunar_tag = "🌙" if b.get("is_lunar") else ""
                solar_hint = f"，國曆 {b['solar_date']}" if b.get("is_lunar") and b.get("solar_date") else ""
                lines.append(f"🎈 {lunar_tag}{b['name']} 的生日在 {b['days_until']} 天後（{b['month']}/{b['day']}{solar_hint}）")
            lines.append("")

        # 天氣
        weather = get_weather("")
        weather_first_period = ""
        for line in weather.split("\n"):
            if "°C" in line or "降雨" in line:
                weather_first_period = line.strip()
                break
        if weather_first_period:
            lines.append(f"🌤️ {weather_first_period}")
            lines.append("")

        # 今日行程
        if today_events:
            lines.append("📅 今日行程：")
            for e in today_events:
                lines.append(f"  • {e['datetime']}  {e['title']}")
            lines.append("")
        else:
            lines.append("📅 今天沒有行程")
            lines.append("")

        # 待辦事項
        if pending_todos:
            lines.append(f"📋 待辦事項（{len(pending_todos)} 項）")
            for t in pending_todos[:5]:
                lines.append(f"  ☐ {t['title']}")
            if len(pending_todos) > 5:
                lines.append(f"  ...還有 {len(pending_todos) - 5} 項")
            lines.append("")

        # 購物清單
        if shopping:
            lines.append(f"🛒 購物清單（{len(shopping)} 項）")
            for s in shopping[:5]:
                lines.append(f"  ☐ {s['item']}")
            if len(shopping) > 5:
                lines.append(f"  ...還有 {len(shopping) - 5} 項")

        text = "\n".join(lines).strip()

        try:
            push_message(group_id, text)
        except Exception as e:
            print(f"[Scheduler Error] push to {group_id}: {e}")


def daily_evening_summary():
    """每晚 9 點推播今日收藏摘要（只推給有收藏的 1 對 1 用戶）"""
    db = Database()
    user_ids = db.get_all_user_ids_with_collections_today()

    for user_id in user_ids:
        items = db.get_today_collections(user_id)
        if not items:
            continue

        category_emoji = {
            "待讀": "📖", "待辦": "✅", "靈感": "💡",
            "帳務": "💰", "工作": "💼", "家庭": "🏠",
        }

        category_counts = {}
        action_items = []
        for item in items:
            cat = item.get("category", "未分類")
            category_counts[cat] = category_counts.get(cat, 0) + 1
            if item.get("status") == "unread":
                action_items.append(item)

        lines = [f"📊 今日收藏摘要（共 {len(items)} 筆）", ""]
        for cat, count in sorted(category_counts.items()):
            emoji = category_emoji.get(cat, "📌")
            lines.append(f"{emoji} {cat}：{count} 筆")

        if action_items:
            need_action = [i for i in action_items
                           if i.get("category") in ("待辦", "帳務", "工作")]
            if need_action:
                lines.append(f"\n⚡ 其中 {len(need_action)} 筆可能需要處理")

        lines.append("\n💡 輸入「我的收藏」可查看完整清單")

        try:
            push_message(user_id, "\n".join(lines))
        except Exception as e:
            print(f"[Scheduler Error] evening summary to {user_id}: {e}")


def generate_recurring_events():
    """每日凌晨檢查週期行程，自動產生未來 7 天的實例"""
    db = Database()
    group_ids = db.get_all_group_ids()
    today = now_tw().date()

    for group_id in group_ids:
        recurring = db.get_recurring_events(group_id)
        for event in recurring:
            recurrence = event.get("recurrence", "")
            if not recurrence:
                continue

            for day_offset in range(1, 8):
                target_date = today + timedelta(days=day_offset)
                if _matches_recurrence(recurrence, target_date):
                    dt_str = target_date.strftime("%Y-%m-%d")
                    time_part = _extract_time(event["datetime"])
                    if time_part:
                        dt_str = f"{dt_str} {time_part}"

                    existing = db.get_upcoming_events(group_id, days=day_offset + 1)
                    already_exists = any(
                        e["title"] == event["title"] and e["datetime"].startswith(target_date.strftime("%Y-%m-%d"))
                        for e in existing
                    )
                    if not already_exists:
                        db.add_event(group_id, event["user_id"], event["title"], dt_str)


def _matches_recurrence(recurrence: str, target_date) -> bool:
    """判斷日期是否符合週期規則"""
    r = recurrence.lower().strip()

    if r == "daily" or r == "每天":
        return True

    weekday_map = {
        "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    }

    # "weekly:三" or "每週三" or "每週一三五"
    weekly_match = re.match(r"(?:weekly:|每週|每周)(.+)", r)
    if weekly_match:
        days_str = weekly_match.group(1)
        for char, day_num in weekday_map.items():
            if char in days_str and target_date.weekday() == day_num:
                return True
        return False

    # "monthly:5" or "每月5號"
    monthly_match = re.match(r"(?:monthly:|每月)(\d+)", r)
    if monthly_match:
        return target_date.day == int(monthly_match.group(1))

    return False


def _extract_time(datetime_str: str) -> str:
    """從 datetime 字串中提取時間部分"""
    m = re.search(r"(\d{2}:\d{2})", datetime_str)
    return m.group(1) if m else ""


def archive_old_events_job():
    """每週日凌晨歸檔超過一年的行程"""
    db = Database()
    count = db.archive_old_events(days_old=365)
    if count > 0:
        print(f"[Scheduler] Archived {count} old events")
