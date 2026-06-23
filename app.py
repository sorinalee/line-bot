"""
LINE Bot — 家庭助理（行程管理 + 待辦事項 + Gemini 自然語言理解）
部署平台：Railway
LLM：Google Gemini API（免費額度）
"""

import os
import json
import re
from datetime import datetime, timedelta, timezone

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from linebot.v3.exceptions import InvalidSignatureError

from database import Database
from gemini_handler import GeminiHandler
from weather_handler import get_weather
from exchange_handler import get_exchange_rate
from scheduler import start_scheduler

# ── 時區設定 ─────────────────────────────────────────────
TW = timezone(timedelta(hours=8))


def now_tw():
    """取得台灣時間"""
    return datetime.now(TW)


# ── 初始化 ──────────────────────────────────────────────
app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
db = Database()
gemini = GeminiHandler(GEMINI_API_KEY)


# ── Webhook 入口 ────────────────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# ── 訊息處理 ────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_msg = event.message.text.strip()
    is_group = hasattr(event.source, "group_id") and event.source.group_id
    group_id = event.source.group_id if is_group else event.source.user_id
    user_id = event.source.user_id

    if is_group:
        # 群組模式：需要觸發詞
        trigger_words = ["小助理", "/", "！", "!"]
        triggered = any(user_msg.startswith(t) for t in trigger_words)
        if not triggered:
            return
        for t in trigger_words:
            if user_msg.startswith(t):
                user_msg = user_msg[len(t):].strip()
                break
    # 1 對 1 模式：直接處理，不需要觸發詞

    # 處理特殊指令（關鍵字直接攔截，不經 Gemini）
    if user_msg in ["幫助", "help", "指令", "?"]:
        result = get_help_text()
    elif user_msg in ["debug", "偵錯", "檢查資料"]:
        result = handle_debug(group_id)
    else:
        result = process_with_gemini(user_msg, group_id, user_id,
                                     is_private=not is_group)

    # 回覆
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        reply = result if isinstance(result, str) else str(result)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)],
            )
        )


# ── 圖片訊息處理（1 對 1 收藏 + OCR）─────────────────────
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    is_group = hasattr(event.source, "group_id") and event.source.group_id
    if is_group:
        return
    user_id = event.source.user_id
    message_id = event.message.id

    try:
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            content = blob_api.get_message_content(message_id)
            image_bytes = content if isinstance(content, bytes) else content.read()

        analysis = gemini.analyze_image(image_bytes)

        category = analysis.get("category", "靈感")
        title = analysis.get("title", "圖片")
        summary = analysis.get("summary", "")
        ocr_text = analysis.get("ocr_text", "")

        db.add_collection(
            user_id=user_id,
            content_type="image",
            category=category,
            title=title,
            summary=summary,
            raw_text=ocr_text,
        )

        lines = [f"📌 已收藏 → {category}", f"📋 {title}"]
        if summary:
            lines.append(f"📝 {summary}")
        if ocr_text:
            lines.append(f"🔍 辨識文字：{ocr_text[:200]}")

        if analysis.get("has_deadline") and analysis.get("deadline_date"):
            deadline = analysis["deadline_date"]
            lines.append(f"⏰ 截止日：{deadline}")
            db.add_event(user_id, user_id, f"[截止] {title}", deadline)
            lines.append("→ 已自動加入行程提醒")

        if analysis.get("has_amount") and analysis.get("amount"):
            lines.append(f"💰 金額：{analysis['amount']}")

        if analysis.get("action_needed"):
            lines.append(f"👉 {analysis['action_needed']}")

        result = "\n".join(lines)
    except Exception as e:
        print(f"[Image Handler Error] {type(e).__name__}: {e}")
        result = "圖片處理失敗，請稍後再試"

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=result)],
            )
        )


# ── Gemini 意圖解析 + 執行 ──────────────────────────────
def process_with_gemini(user_msg: str, group_id: str, user_id: str,
                        is_private: bool = False) -> str:
    """讓 Gemini 解析使用者意圖，回傳結構化 JSON，再執行對應動作。"""

    today = now_tw().strftime("%Y-%m-%d %H:%M (%A)")

    # 取得現有資料作為上下文
    upcoming_events = db.get_upcoming_events(group_id, days=7)
    pending_todos = db.get_todos(group_id, status="pending")
    shopping = db.get_shopping_list(group_id, status="pending")

    mode_hint = "\n模式：1 對 1 個人助理（支援 save_collection）" if is_private else "\n模式：群組家庭助理"

    context = f"""現在時間：{today}{mode_hint}

【未來 7 天行程】
{format_events_for_context(upcoming_events)}

【待辦事項】
{format_todos_for_context(pending_todos)}

【購物清單】
{format_shopping_for_context(shopping)}"""

    intent_json = gemini.parse_intent(user_msg, context)

    if intent_json is None:
        return "抱歉，我沒有聽懂 😅 可以換個方式說說看，或輸入「小助理 幫助」查看使用方式。"

    try:
        action = intent_json.get("action", "chat")
        data = intent_json.get("data", {})

        if action == "add_event":
            return handle_add_event(data, group_id, user_id)
        elif action == "query_events":
            return handle_query_events(data, group_id)
        elif action == "search_events":
            return handle_search_events(data, group_id)
        elif action == "delete_event":
            return handle_delete_event(data, group_id)
        elif action == "update_event":
            return handle_update_event(data, group_id)
        elif action == "add_todo":
            return handle_add_todo(data, group_id, user_id)
        elif action == "complete_todo":
            return handle_complete_todo(data, group_id)
        elif action == "query_todos":
            return handle_query_todos(group_id)
        elif action == "delete_todo":
            return handle_delete_todo(data, group_id)
        elif action == "query_weather":
            location = data.get("location", "")
            return get_weather(location)
        elif action == "add_shopping":
            return handle_add_shopping(data, group_id, user_id)
        elif action == "complete_shopping":
            return handle_complete_shopping(data, group_id)
        elif action == "query_shopping":
            return handle_query_shopping(group_id)
        elif action == "delete_shopping":
            return handle_delete_shopping(data, group_id)
        elif action == "clear_shopping":
            return handle_clear_shopping(group_id)
        elif action == "query_exchange":
            currency = data.get("currency", "")
            amount = data.get("amount", 0)
            return get_exchange_rate(currency, amount)
        elif action == "add_birthday":
            return handle_add_birthday(data, group_id)
        elif action == "query_birthdays":
            return handle_query_birthdays(group_id)
        elif action == "delete_birthday":
            return handle_delete_birthday(data, group_id)
        elif action == "plan_trip":
            return handle_plan_trip(data, group_id, user_id)
        elif action == "save_collection":
            return handle_save_collection(data, user_id)
        elif action == "query_collections":
            return handle_query_collections(data, user_id)
        elif action == "search_collections":
            return handle_search_collections(data, user_id)
        elif action == "summary":
            return handle_summary(group_id)
        elif action == "chat":
            return intent_json.get("reply", "好的，收到！")
        else:
            return intent_json.get("reply", "我不太確定你的意思，可以再說清楚一點嗎？")

    except Exception as e:
        return f"處理時發生錯誤：{str(e)}"


# ── 日期正規化 ──────────────────────────────────────────
def normalize_date(date_str: str) -> str | None:
    """將各種日期格式統一轉成 YYYY-MM-DD，失敗回傳 None"""
    today = now_tw()
    s = date_str.strip()

    # 已經是 YYYY-MM-DD
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", s):
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # YYYY/MM/DD
    if re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", s):
        try:
            dt = datetime.strptime(s, "%Y/%m/%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # MM/DD or M/D（補上今年）
    if re.match(r"^\d{1,2}/\d{1,2}$", s):
        try:
            dt = datetime.strptime(f"{today.year}/{s}", "%Y/%m/%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # MM-DD or M-D（補上今年）
    if re.match(r"^\d{1,2}-\d{1,2}$", s):
        try:
            dt = datetime.strptime(f"{today.year}-{s}", "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 中文格式：X月X日 or X月X號
    m = re.match(r"^(\d{1,2})\s*月\s*(\d{1,2})\s*[日號]?$", s)
    if m:
        try:
            dt = datetime(today.year, int(m.group(1)), int(m.group(2)))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 相對日期（含過去）
    relative = {"前天": -2, "昨天": -1, "今天": 0, "明天": 1, "後天": 2, "大後天": 3}
    if s in relative:
        dt = today + timedelta(days=relative[s])
        return dt.strftime("%Y-%m-%d")

    return None


# ── 動作處理函式 ─────────────────────────────────────────
def handle_add_event(data: dict, group_id: str, user_id: str) -> str:
    title = data.get("title", "未命名行程")
    date_str = data.get("date", "")
    time_str = data.get("time", "")
    recurrence = data.get("recurrence", "")

    if not date_str:
        return "請告訴我行程的日期，例如「7/5 下午三點 看牙醫」"

    normalized = normalize_date(date_str)
    if normalized is None:
        normalized = date_str
        print(f"[WARNING] 無法正規化日期：'{date_str}'，照原樣存入")

    dt_str = f"{normalized} {time_str}".strip()
    db.add_event(group_id, user_id, title, dt_str, recurrence=recurrence)

    reply = f"✅ 已新增行程：\n📅 {dt_str}\n📌 {title}"
    if recurrence:
        reply += f"\n🔁 {recurrence}"
    return reply


def handle_query_events(data: dict, group_id: str) -> str:
    target_date = data.get("target_date", "")

    if target_date:
        normalized = normalize_date(target_date)
        if not normalized:
            normalized = target_date
        events = db.get_events_by_date(group_id, normalized)
        label = normalized
        if not events:
            return f"📅 {label} 沒有行程"
        lines = [f"📅 {label} 的行程：", ""]
        for e in events:
            lines.append(f"• {e['datetime']}  {e['title']}")
        return "\n".join(lines)

    days = data.get("days", 7)
    events = db.get_upcoming_events(group_id, days=days)

    if days <= 1:
        label = "今天"
    elif days <= 3:
        label = f"近 {days} 天"
    else:
        label = f"未來 {days} 天"

    if not events:
        return f"{label}沒有行程，盡情放鬆吧 🎉"

    lines = [f"📅 {label}的行程：", ""]
    for e in events:
        lines.append(f"• {e['datetime']}  {e['title']}")
    return "\n".join(lines)


def handle_search_events(data: dict, group_id: str) -> str:
    keyword = data.get("keyword", "")
    if not keyword:
        return "請告訴我要查什麼，例如「我哪天看過牙醫？」"

    events = db.search_events(group_id, keyword)
    if not events:
        return f"找不到包含「{keyword}」的行程紀錄"

    lines = [f"🔍 包含「{keyword}」的行程紀錄：", ""]
    for e in events:
        lines.append(f"• {e['datetime']}  {e['title']}")
    return "\n".join(lines)


def handle_delete_event(data: dict, group_id: str) -> str:
    keyword = data.get("keyword", "")
    if not keyword:
        return "請告訴我要刪除哪個行程，例如「取消看牙醫」"

    deleted_list = db.delete_event_by_keyword(group_id, keyword)
    if not deleted_list:
        return f"找不到包含「{keyword}」的行程"
    if len(deleted_list) == 1:
        d = deleted_list[0]
        return f"🗑️ 已刪除行程：{d['title']}（{d['datetime']}）"
    lines = [f"🗑️ 已刪除 {len(deleted_list)} 筆行程："]
    for d in deleted_list:
        lines.append(f"  • {d['title']}（{d['datetime']}）")
    return "\n".join(lines)


def handle_update_event(data: dict, group_id: str) -> str:
    keyword = data.get("keyword", "")
    if not keyword:
        return "請告訴我要修改哪個行程，例如「看牙醫改到下週五」"

    new_date = normalize_date(data.get("new_date", "")) if data.get("new_date") else ""
    new_time = data.get("new_time", "")
    new_title = data.get("new_title", "")

    if not new_date and not new_time and not new_title:
        return "請告訴我要改什麼，例如日期、時間或行程名稱"

    updated = db.update_event_by_keyword(
        group_id, keyword,
        new_date=new_date or "",
        new_time=new_time,
        new_title=new_title,
    )
    if not updated:
        return f"找不到包含「{keyword}」的行程"

    return f"📝 已修改行程：{updated['title']}（{updated['datetime']}）"


def handle_add_todo(data: dict, group_id: str, user_id: str) -> str:
    items = data.get("items", [])
    if not items:
        title = data.get("title", "")
        if title:
            items = [title]
        else:
            return "請告訴我要新增什麼待辦事項"

    results = []
    for item in items:
        db.add_todo(group_id, user_id, item)
        results.append(f"  ☐ {item}")

    return "✅ 已新增待辦：\n" + "\n".join(results)


def handle_complete_todo(data: dict, group_id: str) -> str:
    keyword = data.get("keyword", "")
    if not keyword:
        return "請告訴我要完成哪個待辦，例如「買牛奶 完成了」"

    completed = db.complete_todo_by_keyword(group_id, keyword)
    if completed:
        return f"✅ 已完成：{completed['title']}"
    return f"找不到包含「{keyword}」的待辦事項"


def handle_query_todos(group_id: str) -> str:
    todos = db.get_todos(group_id, status="pending")
    if not todos:
        return "目前沒有待辦事項，太棒了！🎉"

    lines = ["📋 待辦清單：", ""]
    for i, t in enumerate(todos, 1):
        lines.append(f"  {i}. ☐ {t['title']}")
    return "\n".join(lines)


def handle_delete_todo(data: dict, group_id: str) -> str:
    keyword = data.get("keyword", "")
    if not keyword:
        return "請告訴我要刪除哪個待辦事項"

    deleted = db.delete_todo_by_keyword(group_id, keyword)
    if deleted:
        return f"🗑️ 已刪除待辦：{deleted['title']}"
    return f"找不到包含「{keyword}」的待辦事項"


def handle_summary(group_id: str) -> str:
    events = db.get_upcoming_events(group_id, days=3)
    todos = db.get_todos(group_id, status="pending")
    shopping = db.get_shopping_list(group_id, status="pending")

    lines = ["📊 目前狀態總覽", ""]

    if events:
        lines.append("【近三天行程】")
        for e in events:
            recur = f" 🔁" if e.get("recurrence") else ""
            lines.append(f"  📅 {e['datetime']}  {e['title']}{recur}")
        lines.append("")

    if todos:
        lines.append(f"【待辦事項】（{len(todos)} 項）")
        for t in todos:
            lines.append(f"  ☐ {t['title']}")
        lines.append("")
    else:
        lines.append("【待辦事項】全部完成！🎉")
        lines.append("")

    if shopping:
        lines.append(f"【購物清單】（{len(shopping)} 項）")
        for s in shopping:
            lines.append(f"  🛒 {s['item']}")
    else:
        lines.append("【購物清單】沒有待買項目")

    if not events and not todos and not shopping:
        return "目前沒有行程、待辦、購物清單，一切清爽！✨"

    return "\n".join(lines)


# ── 購物清單 ───────────────────────────────────────────
def handle_add_shopping(data: dict, group_id: str, user_id: str) -> str:
    items = data.get("items", [])
    if not items:
        item = data.get("item", "")
        if item:
            items = [item]
        else:
            return "請告訴我要買什麼，例如「要買牛奶、雞蛋」"

    results = []
    for item in items:
        db.add_shopping_item(group_id, user_id, item)
        results.append(f"  🛒 {item}")

    return "✅ 已加入購物清單：\n" + "\n".join(results)


def handle_complete_shopping(data: dict, group_id: str) -> str:
    keyword = data.get("keyword", "")
    if not keyword:
        return "請告訴我買了什麼，例如「牛奶買了」"

    completed = db.complete_shopping_item(group_id, keyword)
    if completed:
        return f"✅ 已購買：{completed['item']}"
    return f"購物清單中找不到「{keyword}」"


def handle_query_shopping(group_id: str) -> str:
    pending = db.get_shopping_list(group_id, status="pending")
    if not pending:
        return "購物清單是空的，不需要買東西 🎉"

    lines = ["🛒 購物清單：", ""]
    for i, s in enumerate(pending, 1):
        lines.append(f"  {i}. ☐ {s['item']}")
    return "\n".join(lines)


def handle_delete_shopping(data: dict, group_id: str) -> str:
    keyword = data.get("keyword", "")
    if not keyword:
        return "請告訴我要刪除哪個購物項目"

    deleted = db.delete_shopping_item(group_id, keyword)
    if deleted:
        return f"🗑️ 已從購物清單移除：{deleted['item']}"
    return f"購物清單中找不到「{keyword}」"


def handle_clear_shopping(group_id: str) -> str:
    count = db.clear_bought_items(group_id)
    if count > 0:
        return f"🗑️ 已清除 {count} 個已購買項目"
    return "沒有已購買的項目需要清除"


# ── 生日 ──────────────────────────────────────────────
def handle_add_birthday(data: dict, group_id: str) -> str:
    items = data.get("items", [])

    # 向下相容：如果 Gemini 回傳舊格式（單筆），轉成 items
    if not items and data.get("name"):
        items = [{"name": data["name"], "month": data.get("month", 0),
                  "day": data.get("day", 0), "year": data.get("year"),
                  "is_lunar": data.get("is_lunar", False)}]

    if not items:
        return "請告訴我姓名和生日，例如「媽媽生日是3月15號」或「阿嬤農曆九月初三生日」"

    results = []
    for item in items:
        name = item.get("name", "")
        month = item.get("month", 0)
        day = item.get("day", 0)
        year = item.get("year")
        is_lunar = item.get("is_lunar", False)

        if not name or not month or not day:
            continue

        db.add_birthday(group_id, name, month, day, year, is_lunar=is_lunar)

        cal_type = "農曆" if is_lunar else ""
        date_str = f"{cal_type}{month}/{day}"
        year_str = f"（{year} 年生）" if year else ""
        line = f"  🎂 {name}：{date_str}{year_str}"

        if is_lunar:
            solar = db._lunar_to_solar(month, day, now_tw().year)
            if solar:
                line += f" → 今年國曆 {solar.month}/{solar.day}"

        results.append(line)

    if not results:
        return "請告訴我姓名和生日，例如「媽媽3月15號、爸爸8月20號」"

    return f"✅ 已記住 {len(results)} 位生日：\n" + "\n".join(results)


def handle_query_birthdays(group_id: str) -> str:
    all_bdays = db.get_birthdays(group_id)
    if not all_bdays:
        return "還沒有記錄任何生日，用「小助理 媽媽生日是3月15號」來新增吧！"

    upcoming = db.get_upcoming_birthdays(group_id, days=90)

    lines = ["🎂 生日清單：", ""]
    for b in all_bdays:
        lunar_tag = "（農曆）" if b.get("is_lunar") else ""
        date_str = f"{b['month']}/{b['day']}"
        year_str = f"（{b['year']} 年生）" if b.get("year") else ""
        lines.append(f"  • {b['name']}：{lunar_tag}{date_str}{year_str}")

    if upcoming:
        lines.append("")
        lines.append("📅 近期生日：")
        for b in upcoming:
            lunar_tag = "🌙" if b.get("is_lunar") else ""
            solar_str = f"國曆 {b['solar_date']}" if b.get("is_lunar") and b.get("solar_date") else ""
            if b["days_until"] == 0:
                extra = f" {solar_str}" if solar_str else ""
                lines.append(f"  🎉 {lunar_tag}{b['name']} — 今天！{extra}")
            else:
                extra = f"（{solar_str}）" if solar_str else ""
                lines.append(f"  🎈 {lunar_tag}{b['name']} — {b['days_until']} 天後{extra}")

    return "\n".join(lines)


def handle_delete_birthday(data: dict, group_id: str) -> str:
    name = data.get("name", "")
    if not name:
        return "請告訴我要刪除誰的生日"

    deleted = db.delete_birthday(group_id, name)
    if deleted:
        return f"🗑️ 已刪除 {deleted['name']} 的生日（{deleted['month']}/{deleted['day']}）"
    return f"找不到「{name}」的生日紀錄"


# ── 旅遊規劃 ──────────────────────────────────────────
def handle_plan_trip(data: dict, group_id: str, user_id: str) -> str:
    destination = data.get("destination", "")
    start_date = data.get("start_date", "")
    days = data.get("days", 2)
    preferences = data.get("preferences", "")

    if not destination:
        return "請告訴我你想去哪裡，例如「幫我規劃花蓮三天兩夜」"
    if not start_date:
        tomorrow = now_tw() + timedelta(days=1)
        start_date = tomorrow.strftime("%Y-%m-%d")

    result = gemini.plan_trip(destination, start_date, days, preferences)

    if result.get("error"):
        return f"⚠️ 規劃行程失敗：{result['error']}"

    itinerary = result.get("data")
    if not itinerary:
        return "規劃行程時 AI 未回傳有效資料，請稍後再試"

    saved_count = 0
    lines = [f"🗺️ {destination} {days}天行程規劃：", ""]

    for day_plan in itinerary:
        date = day_plan.get("date", "")
        title = day_plan.get("title", "")
        activities = day_plan.get("activities", [])

        if date and title:
            db.add_event(group_id, user_id, title, date)
            saved_count += 1

        lines.append(f"📅 {date}　{title}")
        for act in activities:
            t = act.get("time", "")
            a = act.get("activity", "")
            lines.append(f"  • {t} {a}")
        lines.append("")

    lines.append(f"✅ 已將 {saved_count} 天行程存入行程表")
    lines.append("💡 輸入「小助理 這週行程」即可查看")

    return "\n".join(lines)


# ── 收藏功能 ─────────────────────────────────────────────
CATEGORY_EMOJI = {
    "待讀": "📖", "待辦": "✅", "靈感": "💡",
    "帳務": "💰", "工作": "💼", "家庭": "🏠",
}


def handle_save_collection(data: dict, user_id: str) -> str:
    content = data.get("content", "")
    if not content:
        return "請告訴我要收藏什麼內容"

    has_url = "http://" in content or "https://" in content
    analysis = gemini.analyze_collection(content)

    category = analysis.get("category", "靈感")
    title = analysis.get("title", content[:10])
    summary = analysis.get("summary", content[:50])
    source_url = content.strip() if has_url and "\n" not in content.strip() else ""

    db.add_collection(
        user_id=user_id,
        content_type="url" if has_url else "text",
        category=category,
        title=title,
        summary=summary,
        raw_text=content,
        source_url=source_url,
    )

    emoji = CATEGORY_EMOJI.get(category, "📌")
    lines = [f"{emoji} 已收藏 → {category}", f"📋 {title}"]
    if summary:
        lines.append(f"📝 {summary}")

    if analysis.get("has_deadline") and analysis.get("deadline_date"):
        deadline = analysis["deadline_date"]
        lines.append(f"⏰ 截止日：{deadline}")
        db.add_event(user_id, user_id, f"[截止] {title}", deadline)
        lines.append("→ 已自動加入行程提醒")

    if analysis.get("action_needed"):
        lines.append(f"👉 {analysis['action_needed']}")

    return "\n".join(lines)


def handle_query_collections(data: dict, user_id: str) -> str:
    category = data.get("category", "")
    items = db.get_collections(user_id, category=category)

    if not items:
        label = f"「{category}」類的" if category else ""
        return f"目前沒有{label}收藏"

    label = f"「{category}」" if category else "所有"
    lines = [f"📚 {label}收藏（共 {len(items)} 筆）：", ""]
    for item in items[:15]:
        emoji = CATEGORY_EMOJI.get(item["category"], "📌")
        date = item["created_at"].strftime("%m/%d") if hasattr(item["created_at"], "strftime") else str(item["created_at"])[:5]
        lines.append(f"{emoji} [{item['category']}] {item['title']}（{date}）")
        if item.get("summary"):
            lines.append(f"   {item['summary'][:40]}")
    if len(items) > 15:
        lines.append(f"\n...還有 {len(items) - 15} 筆")
    return "\n".join(lines)


def handle_search_collections(data: dict, user_id: str) -> str:
    keyword = data.get("keyword", "")
    if not keyword:
        return "請告訴我要找什麼，例如「找一下停車費」"

    items = db.search_collections(user_id, keyword)
    if not items:
        return f"找不到包含「{keyword}」的收藏"

    lines = [f"🔍 包含「{keyword}」的收藏（{len(items)} 筆）：", ""]
    for item in items[:10]:
        emoji = CATEGORY_EMOJI.get(item["category"], "📌")
        lines.append(f"{emoji} [{item['category']}] {item['title']}")
        if item.get("summary"):
            lines.append(f"   {item['summary'][:40]}")
    return "\n".join(lines)


# ── Debug ──────────────────────────────────────────────
def handle_debug(group_id: str) -> str:
    """列出資料庫中的原始資料，方便偵錯"""
    today = now_tw().strftime("%Y-%m-%d")
    all_events = db.get_all_events(group_id)
    todos = db.get_todos(group_id, status="pending")

    lines = [f"🔍 偵錯資訊（今天={today}）", ""]

    if all_events:
        lines.append(f"【所有行程】共 {len(all_events)} 筆")
        for e in all_events:
            lines.append(f"  id={e['id']} datetime=\"{e['datetime']}\" title=\"{e['title']}\"")
    else:
        lines.append("【所有行程】（無）")

    lines.append("")

    if todos:
        lines.append(f"【待辦事項】共 {len(todos)} 筆")
        for t in todos:
            lines.append(f"  id={t['id']} title=\"{t['title']}\"")
    else:
        lines.append("【待辦事項】（無）")

    return "\n".join(lines)


# ── 輔助函式 ─────────────────────────────────────────────
def format_events_for_context(events: list) -> str:
    if not events:
        return "（無）"
    return "\n".join(f"- {e['datetime']} {e['title']}" for e in events)


def format_todos_for_context(todos: list) -> str:
    if not todos:
        return "（無）"
    return "\n".join(f"- {t['title']}" for t in todos)


def format_shopping_for_context(shopping: list) -> str:
    if not shopping:
        return "（無）"
    return "\n".join(f"- {s['item']}" for s in shopping)


def get_help_text() -> str:
    return """🤖 家庭助理使用說明

跟我說話時請以「小助理」或「/」開頭，例如：

【行程管理】
• 小助理 下週三下午兩點看牙醫
• 小助理 每週三晚上八點倒垃圾（週期行程）
• 小助理 每月5號繳房租（每月重複）
• 小助理 這週有什麼行程？
• 小助理 取消看牙醫

【待辦事項】
• 小助理 待辦：繳電話費、寄包裹
• 小助理 電話費繳了
• 小助理 待辦清單

【購物清單】
• 小助理 要買牛奶、雞蛋、衛生紙
• 小助理 牛奶買了
• 小助理 購物清單
• 小助理 不用買衛生紙了

【生日提醒】
• 小助理 媽媽生日是3月15號
• 小助理 爸爸1965年8月20日生
• 小助理 阿嬤農曆九月初三生日
• 小助理 生日清單
• 小助理 刪除媽媽的生日

【匯率查詢】
• 小助理 美金匯率
• 小助理 100美金多少台幣
• 小助理 日幣匯率

【旅遊規劃】
• 小助理 幫我規劃花蓮三天兩夜
• 小助理 7/10出發去台南玩兩天

【其他】
• 小助理 天氣（查詢天氣預報）
• 小助理 目前狀態（總覽）
• 小助理 幫助

💡 用自然的方式說就好，我會自己理解！
⏰ 每天早上 7:30 會自動推播今日行程和天氣"""


# ── 啟動排程 ───────────────────────────────────────────
start_scheduler(app)

# ── 啟動 ────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
