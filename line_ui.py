"""
LINE UI 模組 — Quick Reply + Flex Message 建構器
"""

import re
from urllib.parse import quote, urlparse

from linebot.v3.messaging import (
    FlexMessage,
    FlexContainer,
    QuickReply,
    QuickReplyItem,
    MessageAction,
    URIAction,
    TextMessage,
)


def _safe_uri(url: str) -> str | None:
    """驗證並清理 URL，不合規回傳 None"""
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://", "line://")):
        return None
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        if not all(ord(c) < 128 for c in parsed.netloc):
            return url[:1000] if len(url) <= 1000 else None
        uri_safe = "/:@!$&()*+,;=-._~"
        safe = f"{parsed.scheme}://{parsed.netloc}{quote(parsed.path, safe=uri_safe)}"
        if parsed.query:
            safe += "?" + quote(parsed.query, safe=uri_safe + "?=&")
        if parsed.fragment:
            safe += "#" + quote(parsed.fragment, safe=uri_safe)
        if len(safe) > 1000:
            return None
        return safe
    except Exception:
        return None

# ── 分類配色 ─────────────────────────────────────────────
CATEGORY_COLORS = {
    "待讀": "#4A90D9",
    "待辦": "#27AE60",
    "靈感": "#F39C12",
    "帳務": "#E74C3C",
    "工作": "#8E44AD",
    "家庭": "#E67E22",
    "工具箱": "#34495E",
}

CATEGORY_EMOJI = {
    "待讀": "📖", "待辦": "✅", "靈感": "💡",
    "帳務": "💰", "工作": "💼", "家庭": "🏠", "工具箱": "🧰",
}


# ── Quick Reply ──────────────────────────────────────────

def build_quick_reply(is_group: bool = True) -> QuickReply:
    if is_group:
        items = [
            ("📅 今天行程", "今天行程"),
            ("✅ 待辦", "待辦"),
            ("🛒 購物清單", "購物清單"),
            ("🎂 生日", "生日清單"),
            ("🌤 天氣", "天氣"),
            ("📊 總覽", "目前狀態"),
            ("❓ 幫助", "幫助"),
        ]
    else:
        items = [
            ("📚 我的收藏", "我的收藏"),
            ("📅 今天行程", "今天行程"),
            ("✅ 待辦", "待辦"),
            ("🌤 天氣", "天氣"),
            ("🔄 重新辨識", "重新辨識"),
            ("❓ 幫助", "幫助"),
        ]
    return QuickReply(
        items=[
            QuickReplyItem(action=MessageAction(label=label, text=text))
            for label, text in items
        ]
    )


def make_text_message(text: str, is_group: bool = True) -> TextMessage:
    return TextMessage(text=text, quick_reply=build_quick_reply(is_group))


# ── Flex: 收藏清單 ────────────────────────────────────────

def _collection_bubble(item: dict) -> dict:
    cat = item.get("category") or "未分類"
    color = CATEGORY_COLORS.get(cat, "#888888")
    emoji = CATEGORY_EMOJI.get(cat, "📌")
    title = (item.get("title") or "")[:30]
    cid = item.get("id") or 0
    source_url = item.get("source_url") or ""
    date_str = ""
    created_at = item.get("created_at")
    if hasattr(created_at, "strftime"):
        date_str = created_at.strftime("%m/%d")
    elif created_at:
        date_str = str(created_at)[:5]

    body_contents = [
        {
            "type": "text",
            "text": f"#{cid} {title}" if title else f"#{cid}（無標題）",
            "weight": "bold",
            "size": "md",
            "wrap": True,
        },
    ]

    summary = item.get("summary") or ""
    if summary:
        summary_lines = summary.split("\n")
        first_line = (summary_lines[0][:80]).strip() or summary.strip()[:80] or "（無摘要）"
        body_contents.append({
            "type": "text",
            "text": first_line,
            "size": "sm",
            "color": "#555555",
            "wrap": True,
            "margin": "sm",
        })
        bullet_lines = [sl.strip() for sl in summary_lines[1:] if sl.strip().startswith("•")]
        for bl in bullet_lines[:4]:
            body_contents.append({
                "type": "text",
                "text": bl,
                "size": "xs",
                "color": "#666666",
                "wrap": True,
            })

    if item.get("has_image"):
        body_contents.append({
            "type": "text",
            "text": "📷 有暫存圖片待辨識",
            "size": "xs",
            "color": "#E74C3C",
            "margin": "sm",
        })

    header_contents = [
        {
            "type": "text",
            "text": f"{emoji} {cat}",
            "color": "#FFFFFF",
            "weight": "bold",
            "size": "sm",
        },
    ]
    if date_str:
        header_contents.append({
            "type": "text",
            "text": date_str,
            "color": "#FFFFFFCC",
            "size": "xs",
            "align": "end",
        })

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "horizontal",
            "contents": header_contents,
            "backgroundColor": color,
            "paddingAll": "12px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "paddingAll": "12px",
            "spacing": "xs",
        },
    }

    footer_buttons = []
    safe_url = _safe_uri(source_url)
    if safe_url:
        footer_buttons.append({
            "type": "button",
            "action": {"type": "uri", "label": "開啟連結", "uri": safe_url},
            "style": "primary",
            "height": "sm",
            "color": color,
        })
    footer_buttons.append({
        "type": "button",
        "action": {"type": "message", "label": f"修改 #{cid}", "text": f"修改收藏 {cid}"},
        "style": "link",
        "height": "sm",
    })
    footer_buttons.append({
        "type": "button",
        "action": {"type": "message", "label": f"刪除 #{cid}", "text": f"刪除收藏 {cid}"},
        "style": "link",
        "height": "sm",
        "color": "#E74C3C",
    })

    bubble["footer"] = {
        "type": "box",
        "layout": "vertical",
        "contents": footer_buttons,
        "spacing": "xs",
        "paddingAll": "10px",
    }

    return bubble


def build_collection_flex(items: list, title: str = "我的收藏") -> FlexMessage:
    bubbles = [_collection_bubble(item) for item in items[:12]]
    if not bubbles:
        return None

    if len(bubbles) == 1:
        container = bubbles[0]
    else:
        container = {"type": "carousel", "contents": bubbles}

    alt_text = f"📚 {title}（{len(items)} 筆）"
    return FlexMessage(
        alt_text=alt_text,
        contents=FlexContainer.from_dict(container),
        quick_reply=build_quick_reply(is_group=False),
    )


def build_collection_text(items: list, title: str = "我的收藏") -> str:
    """Flex 失敗時的純文字收藏清單"""
    lines = [f"📚 {title}（共 {len(items)} 筆）"]
    for item in items[:10]:
        cat = item.get("category") or "未分類"
        emoji = CATEGORY_EMOJI.get(cat, "📌")
        cid = item.get("id") or 0
        t = (item.get("title") or "（無標題）")[:30]
        lines.append(f"\n{emoji} #{cid} [{cat}] {t}")
        summary = item.get("summary") or ""
        if summary:
            first = summary.split("\n")[0][:60]
            lines.append(f"   {first}")
        url = item.get("source_url") or ""
        if url:
            lines.append(f"   🔗 {url}")
        lines.append(f"   → 輸入「刪除收藏 {cid}」可刪除")
    if len(items) > 10:
        lines.append(f"\n...還有 {len(items) - 10} 筆")
    lines.append("\n💡 輸入「清空收藏」可刪除全部")
    return "\n".join(lines)


# ── Flex: 收藏儲存確認 ───────────────────────────────────

def build_save_confirmation_flex(category: str, title: str, summary: str,
                                  key_points: list = None, source_url: str = "",
                                  extra_info: list = None) -> FlexMessage:
    category = category or "未分類"
    title = title or "（無標題）"
    summary = summary or ""
    source_url = source_url or ""
    color = CATEGORY_COLORS.get(category, "#888888")
    emoji = CATEGORY_EMOJI.get(category, "📌")

    body_contents = []
    if summary:
        body_contents.append({
            "type": "text",
            "text": summary,
            "size": "sm",
            "color": "#555555",
            "wrap": True,
        })

    if key_points:
        body_contents.append({"type": "separator", "margin": "md"})
        body_contents.append({
            "type": "text",
            "text": "📌 重點",
            "weight": "bold",
            "size": "sm",
            "margin": "md",
        })
        for pt in key_points[:5]:
            body_contents.append({
                "type": "text",
                "text": f"• {pt}",
                "size": "xs",
                "color": "#666666",
                "wrap": True,
            })

    if extra_info:
        body_contents.append({"type": "separator", "margin": "md"})
        for info in extra_info:
            body_contents.append({
                "type": "text",
                "text": info,
                "size": "sm",
                "wrap": True,
                "margin": "sm",
            })

    if not body_contents:
        body_contents.append({
            "type": "text",
            "text": "已收藏",
            "size": "sm",
            "color": "#999999",
        })

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"{emoji} 已收藏 → {category}",
                    "color": "#FFFFFF",
                    "weight": "bold",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": title,
                    "color": "#FFFFFFDD",
                    "size": "md",
                    "weight": "bold",
                    "wrap": True,
                    "margin": "sm",
                },
            ],
            "backgroundColor": color,
            "paddingAll": "14px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "paddingAll": "12px",
            "spacing": "xs",
        },
    }

    safe_url = _safe_uri(source_url)
    if safe_url:
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "contents": [{
                "type": "button",
                "action": {"type": "uri", "label": "開啟連結", "uri": safe_url},
                "style": "primary",
                "height": "sm",
                "color": color,
            }],
            "paddingAll": "10px",
        }

    return FlexMessage(
        alt_text=f"{emoji} 已收藏：{title}",
        contents=FlexContainer.from_dict(bubble),
        quick_reply=build_quick_reply(is_group=False),
    )


# ── Flex: 行程清單 ────────────────────────────────────────

def build_events_flex(events: list, label: str, is_group: bool = True) -> FlexMessage:
    body_contents = []
    for e in events[:15]:
        dt_str = e.get("datetime", "") or "（未定）"
        title = e.get("title", "") or "（無標題）"
        recur = " 🔁" if e.get("recurrence") else ""
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": dt_str, "size": "xs", "color": "#4A90D9",
                 "flex": 4, "wrap": True},
                {"type": "text", "text": f"{title}{recur}", "size": "sm",
                 "flex": 6, "wrap": True},
            ],
            "margin": "md",
        })

    if not body_contents:
        return None

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [{
                "type": "text",
                "text": f"📅 {label}的行程",
                "weight": "bold",
                "color": "#FFFFFF",
                "size": "md",
            }],
            "backgroundColor": "#4A90D9",
            "paddingAll": "14px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "paddingAll": "12px",
        },
    }

    return FlexMessage(
        alt_text=f"📅 {label}的行程（{len(events)} 項）",
        contents=FlexContainer.from_dict(bubble),
        quick_reply=build_quick_reply(is_group),
    )


# ── Flex: 待辦清單 ────────────────────────────────────────

def build_todos_flex(todos: list, is_group: bool = True) -> FlexMessage:
    body_contents = []
    for i, t in enumerate(todos[:15], 1):
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": f"{i}.", "size": "sm", "color": "#999999",
                 "flex": 1},
                {"type": "text", "text": f"☐ {t['title']}", "size": "sm",
                 "flex": 9, "wrap": True},
            ],
            "margin": "sm",
        })

    if not body_contents:
        return None

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "📋 待辦清單", "weight": "bold",
                 "color": "#FFFFFF", "size": "md"},
                {"type": "text", "text": f"{len(todos)} 項", "color": "#FFFFFFCC",
                 "size": "sm", "align": "end"},
            ],
            "backgroundColor": "#27AE60",
            "paddingAll": "14px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "paddingAll": "12px",
        },
    }

    return FlexMessage(
        alt_text=f"📋 待辦清單（{len(todos)} 項）",
        contents=FlexContainer.from_dict(bubble),
        quick_reply=build_quick_reply(is_group),
    )


# ── Flex: 購物清單 ────────────────────────────────────────

def build_shopping_flex(items: list, is_group: bool = True) -> FlexMessage:
    body_contents = []
    for s in items[:15]:
        body_contents.append({
            "type": "text",
            "text": f"🛒 {s['item']}",
            "size": "sm",
            "wrap": True,
            "margin": "sm",
        })

    if not body_contents:
        return None

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "🛒 購物清單", "weight": "bold",
                 "color": "#FFFFFF", "size": "md"},
                {"type": "text", "text": f"{len(items)} 項", "color": "#FFFFFFCC",
                 "size": "sm", "align": "end"},
            ],
            "backgroundColor": "#E67E22",
            "paddingAll": "14px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "paddingAll": "12px",
        },
    }

    return FlexMessage(
        alt_text=f"🛒 購物清單（{len(items)} 項）",
        contents=FlexContainer.from_dict(bubble),
        quick_reply=build_quick_reply(is_group),
    )


# ── Flex: 總覽 ────────────────────────────────────────────

def build_summary_flex(events: list, todos: list, shopping: list,
                       is_group: bool = True) -> FlexMessage:
    sections = []

    if events:
        sections.append({
            "type": "text", "text": "📅 近三天行程",
            "weight": "bold", "size": "sm", "margin": "lg",
        })
        for e in events[:5]:
            recur = " 🔁" if e.get("recurrence") else ""
            sections.append({
                "type": "text",
                "text": f"  {e['datetime']}  {e['title']}{recur}",
                "size": "xs", "color": "#555555", "wrap": True,
            })

    if todos:
        sections.append({
            "type": "text", "text": f"✅ 待辦事項（{len(todos)} 項）",
            "weight": "bold", "size": "sm", "margin": "lg",
        })
        for t in todos[:5]:
            sections.append({
                "type": "text", "text": f"  ☐ {t['title']}",
                "size": "xs", "color": "#555555", "wrap": True,
            })
    else:
        sections.append({
            "type": "text", "text": "✅ 待辦事項全部完成！🎉",
            "weight": "bold", "size": "sm", "margin": "lg",
        })

    if shopping:
        sections.append({
            "type": "text", "text": f"🛒 購物清單（{len(shopping)} 項）",
            "weight": "bold", "size": "sm", "margin": "lg",
        })
        for s in shopping[:5]:
            sections.append({
                "type": "text", "text": f"  {s['item']}",
                "size": "xs", "color": "#555555", "wrap": True,
            })

    if not sections:
        return None

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [{
                "type": "text", "text": "📊 目前狀態總覽",
                "weight": "bold", "color": "#FFFFFF", "size": "md",
            }],
            "backgroundColor": "#34495E",
            "paddingAll": "14px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": sections,
            "paddingAll": "12px",
        },
    }

    return FlexMessage(
        alt_text="📊 目前狀態總覽",
        contents=FlexContainer.from_dict(bubble),
        quick_reply=build_quick_reply(is_group),
    )
