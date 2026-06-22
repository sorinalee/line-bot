"""
圖片生成模組 — 早安圖等圖片生成功能
使用 google-genai SDK + Gemini 2.5 Flash Image 生成圖片
圖片透過 Catbox.moe 匿名上傳取得公開 URL 供 LINE 傳送
"""

import os
import io
import random
import requests
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

IMAGE_MODEL = "gemini-2.5-flash-image"

MORNING_THEMES = [
    ("Chinese ink wash painting", "中國風山水畫"),
    ("cute animals illustration", "可愛小動物"),
    ("modern city lifestyle", "現代都會風格"),
    ("beautiful natural scenery", "美麗自然景色"),
    ("Japanese style illustration", "日式和風插畫"),
    ("European garden scene", "歐洲花園風格"),
    ("tropical beach scenery", "熱帶海灘風景"),
    ("warm family illustration", "溫馨家庭插畫"),
    ("watercolor floral art", "水彩花卉風格"),
    ("cute cartoon style", "童趣卡通風格"),
]


def _get_client():
    return genai.Client(api_key=GEMINI_API_KEY)


def _generate_image(prompt: str) -> tuple[bytes | None, str]:
    """呼叫 Gemini 生成圖片，回傳 (image_bytes, text_content)"""
    client = _get_client()
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    image_data = None
    text_content = ""

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            image_data = part.inline_data.data
        elif part.text:
            text_content = part.text.strip()

    return image_data, text_content


def generate_morning_image() -> dict:
    """生成早安圖，回傳 {"url": "...", "text": "..."} 或 {"error": "..."}"""
    if not GEMINI_API_KEY:
        return {"error": "Gemini API 尚未設定"}

    theme_en, theme_zh = random.choice(MORNING_THEMES)

    prompt = (
        f"Generate a bright, warm 'Good Morning' greeting card illustration.\n"
        f"Style: {theme_en}.\n"
        f"Requirements:\n"
        f"- Include the large Chinese characters '早安' prominently\n"
        f"- Add a short positive Chinese phrase below it\n"
        f"- Bright, warm, hopeful mood\n"
        f"- Text must be clearly readable against the background\n"
        f"- Square format, high quality illustration"
    )

    try:
        image_data, text_content = _generate_image(prompt)

        if not image_data:
            return {"error": "未能生成圖片，請稍後再試"}

        img_url = _upload_to_catbox(image_data)
        if not img_url:
            return {"error": "圖片上傳失敗，請稍後再試"}

        return {"url": img_url, "text": f"☀️ 今日主題：{theme_zh}", "theme": theme_zh}

    except Exception as e:
        print(f"[Image Error] {e}")
        return {"error": f"生成圖片時發生錯誤：{str(e)}"}


def generate_custom_image(prompt: str) -> dict:
    """根據自訂 prompt 生成圖片"""
    if not GEMINI_API_KEY:
        return {"error": "Gemini API 尚未設定"}

    try:
        image_data, text_content = _generate_image(prompt)

        if not image_data:
            return {"error": "未能生成圖片，請稍後再試"}

        img_url = _upload_to_catbox(image_data)
        if not img_url:
            return {"error": "圖片上傳失敗，請稍後再試"}

        return {"url": img_url, "text": text_content}

    except Exception as e:
        print(f"[Image Error] {e}")
        return {"error": f"生成圖片時發生錯誤：{str(e)}"}


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
