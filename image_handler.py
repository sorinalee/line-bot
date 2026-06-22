"""
圖片生成模組 — 早安圖等圖片生成功能
使用 google-genai SDK + Imagen 3 (免費版) 生成圖片
圖片透過 Catbox.moe 匿名上傳取得公開 URL 供 LINE 傳送
"""

import os
import io
import random
import requests
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Imagen 模型名稱（免費版 Nano Banana）
IMAGEN_MODEL = "imagen-4.0-fast-generate-001"

MORNING_THEMES_EN = [
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


def _generate_with_imagen(prompt: str) -> bytes | None:
    """呼叫 Imagen 3 生成圖片，回傳 image_bytes"""
    client = _get_client()
    response = client.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
        ),
    )

    if response.generated_images:
        return response.generated_images[0].image.image_bytes
    return None


def generate_morning_image() -> dict:
    """生成早安圖，回傳 {"url": "...", "text": "..."} 或 {"error": "..."}"""
    if not GEMINI_API_KEY:
        return {"error": "Gemini API 尚未設定"}

    theme_en, theme_zh = random.choice(MORNING_THEMES_EN)

    prompt = (
        f"A bright, warm, and hopeful 'Good Morning' greeting card illustration. "
        f"Style: {theme_en}. "
        f"The image should feature the large Chinese characters '早安' (Good Morning) "
        f"prominently displayed with clear contrast against the background. "
        f"Include a short positive phrase in Chinese below it. "
        f"The overall mood should be uplifting, colorful, and full of positive energy. "
        f"Square format, high quality illustration."
    )

    try:
        image_data = _generate_with_imagen(prompt)

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
        image_data = _generate_with_imagen(prompt)

        if not image_data:
            return {"error": "未能生成圖片，請稍後再試"}

        img_url = _upload_to_catbox(image_data)
        if not img_url:
            return {"error": "圖片上傳失敗，請稍後再試"}

        return {"url": img_url, "text": ""}

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
