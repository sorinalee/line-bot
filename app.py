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
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

from database import Database
from gemini_handler import GeminiHandler
from weather_handler import get_weather

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
    group_id = getattr(event.source, "group_id", None) or event.source.user_id
    user_id = event.source.user_id

    # 觸發詞（可自行修改名稱）
    trigger_words = ["小助理", "/", "！", "!"]
    triggered = any(user_msg.startswith(t) for t in trigger_words)

    if not triggered:
        return

    # 去掉觸發詞
    for t in trigger_words:
        if user_msg.startswith(t):
            user_msg = user_msg[len(t):].strip()
            break

    # 處理特殊指令
    if user_msg in ["幫助", "help", "指令", "?"]:
        reply = get_help_text()
    elif user_msg in ["debug", "偵錯", "檢查資料"]:
        reply = handle_debug(group_id)
    else:
        reply = process_with_gemini(user_msg, group_id, user_id)

    # 回覆
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)],
            )
        )


# ── Gemini 意圖解析 + 執行 ──────────────────────────────
def process_with_gemini(user_msg: str, group_id: str, user_id: str) -> str:
    """讓 Gemini 解析使用者意圖，回傳結構化 JSON，再執行對應動作。"""

    today = now_tw().strftime("%Y-%m-%d %H:%M (%A)")

    # 取得現有資料作為上下文
    upcoming_events = db.get_upcoming_events(group_id, days=7)
    pending_todos = db.get_todos(group_id, status="pending")

    context = f"""現在時間：{today}

【未來 7 天行程】
{format_events_for_context(upcoming_events)}

【待辦事項】
{format_todos_for_context(pending_todos)}"""

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

    if not date_str:
        return "請告訴我行程的日期，例如「7/5 下午三點 看牙醫」"

    normalized = normalize_date(date_str)
    if normalized is None:
        normalized = date_str  # 無法解析就照原樣存，但記錄警告
        print(f"[WARNING] 無法正規化日期：'{date_str}'，照原樣存入")

    dt_str = f"{normalized} {time_str}".strip()
    db.add_event(group_id, user_id, title, dt_str)
    return f"✅ 已新增行程：\n📅 {dt_str}\n📌 {title}"


def handle_query_events(data: dict, group_id: str) -> str:
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

    deleted = db.delete_event_by_keyword(group_id, keyword)
    if deleted:
        return f"🗑️ 已刪除行程：{deleted['title']}（{deleted['datetime']}）"
    return f"找不到包含「{keyword}」的行程"


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

    lines = ["📊 目前狀態總覽", ""]

    if events:
        lines.append("【近三天行程】")
        for e in events:
            lines.append(f"  📅 {e['datetime']}  {e['title']}")
        lines.append("")

    if todos:
        lines.append(f"【待辦事項】（{len(todos)} 項）")
        for t in todos:
            lines.append(f"  ☐ {t['title']}")
    else:
        lines.append("【待辦事項】全部完成！🎉")

    if not events and not todos:
        return "目前沒有行程也沒有待辦，一切清爽！✨"

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


def get_help_text() -> str:
    return """🤖 家庭助理使用說明

跟我說話時請以「小助理」或「/」開頭，例如：

【行程管理】
• 小助理 下週三下午兩點看牙醫
• 小助理 這週有什麼行程？
• 小助理 取消看牙醫

【待辦事項】
• 小助理 要買牛奶、雞蛋、衛生紙
• 小助理 牛奶買了
• 小助理 待辦清單
• 小助理 刪掉衛生紙

【其他】
• 小助理 目前狀態
• 小助理 幫助
• 小助理 debug（查看資料庫原始資料）

💡 用自然的方式說就好，我會自己理解！"""


# ── 啟動 ────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
