"""
圖片生成模組 — 早安圖等圖片生成功能
使用 Pollinations.ai 免費 AI 圖片生成（無需 API Key）
圖片透過 Catbox.moe 匿名上傳取得公開 URL 供 LINE 傳送
"""

import os
import io
import random
import requests
from urllib.parse import quote

MORNING_THEMES = [
    ("Chinese ink wash painting with mountains and river", "中國風山水畫"),
    ("cute fluffy animals like cats and dogs", "可愛小動物"),
    ("modern city sunrise skyline", "現代都會風格"),
    ("beautiful natural scenery with flowers and sunshine", "美麗自然景色"),
    ("Japanese zen garden illustration", "日式和風插畫"),
    ("European flower garden with morning light", "歐洲花園風格"),
    ("tropical beach with palm trees and sunrise", "熱帶海灘風景"),
    ("warm cozy family breakfast scene", "溫馨家庭插畫"),
    ("watercolor painting of spring flowers", "水彩花卉風格"),
    ("cute cartoon characters greeting", "童趣卡通風格"),
]


def generate_morning_image() -> dict:
    """生成早安圖，回傳 {"url": "...", "text": "..."} 或 {"error": "..."}"""
    theme_en, theme_zh = random.choice(MORNING_THEMES)

    prompt = (
        f"A bright cheerful Good Morning greeting card, {theme_en}, "
        f"with large beautiful Chinese text '早安' (Good Morning) prominently displayed, "
        f"warm golden sunlight, positive uplifting mood, "
        f"high quality digital illustration, square format"
    )

    try:
        image_bytes = _generate_with_pollinations(prompt)
        if not image_bytes:
            return {"error": "圖片生成失敗，請稍後再試"}

        img_url = _upload_to_catbox(image_bytes)
        if not img_url:
            return {"error": "圖片上傳失敗，請稍後再試"}

        return {"url": img_url, "text": f"☀️ 今日主題：{theme_zh}", "theme": theme_zh}

    except Exception as e:
        print(f"[Image Error] {e}")
        return {"error": f"生成圖片時發生錯誤：{str(e)}"}


def generate_custom_image(prompt: str) -> dict:
    """根據自訂 prompt 生成圖片"""
    try:
        image_bytes = _generate_with_pollinations(prompt)
        if not image_bytes:
            return {"error": "圖片生成失敗，請稍後再試"}

        img_url = _upload_to_catbox(image_bytes)
        if not img_url:
            return {"error": "圖片上傳失敗，請稍後再試"}

        return {"url": img_url, "text": ""}

    except Exception as e:
        print(f"[Image Error] {e}")
        return {"error": f"生成圖片時發生錯誤：{str(e)}"}


def _generate_with_pollinations(prompt: str) -> bytes | None:
    """透過 Pollinations.ai 免費生成圖片，回傳 image bytes"""
    encoded = quote(prompt)
    seed = random.randint(1, 999999)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1024&height=1024&seed={seed}&nologo=true"
    )

    resp = requests.get(url, timeout=60)
    if resp.status_code == 200 and len(resp.content) > 1000:
        return resp.content
    print(f"[Pollinations Error] status={resp.status_code} size={len(resp.content)}")
    return None


def _upload_to_catbox(image_bytes: bytes) -> str | None:
    """上傳圖片到 Catbox.moe（免費、免 API Key），回傳公開 HTTPS URL"""
    try:
        files = {
            "fileToUpload": ("image.png", io.BytesIO(image_bytes), "image/png"),
        }
        data = {"reqtype": "fileupload"}
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            files=files,
            data=data,
            timeout=60,
        )
        if resp.status_code == 200 and resp.text.startswith("https://"):
            return resp.text.strip()
        print(f"[Catbox Error] status={resp.status_code} body={resp.text}")
        return None
    except Exception as e:
        print(f"[Catbox Upload Error] {e}")
        return None
