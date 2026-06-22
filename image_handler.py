"""
Gemini 圖片生成模組 — 早安圖等圖片生成功能
使用 Gemini 2.0 Flash 的原生圖片生成能力
圖片透過 Catbox.moe 匿名上傳取得公開 URL 供 LINE 傳送（免費、免 API Key）
"""

import os
import io
import random
import requests
import google.generativeai as genai
from google.generativeai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

MORNING_THEMES = [
    "中國風山水畫",
    "可愛小動物",
    "現代都會風格",
    "美麗自然景色",
    "日式和風插畫",
    "歐洲花園風格",
    "熱帶海灘風景",
    "溫馨家庭插畫",
    "水彩花卉風格",
    "童趣卡通風格",
]


def generate_morning_image() -> dict:
    """生成早安圖，回傳 {"url": "...", "text": "..."} 或 {"error": "..."}"""
    if not GEMINI_API_KEY:
        return {"error": "Gemini API 尚未設定"}

    theme = random.choice(MORNING_THEMES)

    prompt = f"""請生成一張早安圖片。

主題風格：{theme}

要求：
- 圖片中要有明顯的「早安」中文字樣
- 搭配一句簡短的正向短語（也顯示在圖片上）
- 畫面明亮、溫馨
- 文字需與背景對比清晰、容易閱讀
- 使用正向且充滿希望的視覺元素
- 圖片比例 1:1
- 高品質插圖風格

請生成圖片。"""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        response = model.generate_content(
            prompt,
            generation_config=types.GenerationConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        image_data = None
        text_content = ""

        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_data = part.inline_data.data
            elif hasattr(part, "text") and part.text:
                text_content = part.text.strip()

        if not image_data:
            return {"error": "Gemini 未能生成圖片，請稍後再試"}

        img_url = _upload_to_catbox(image_data)
        if not img_url:
            return {"error": "圖片上傳失敗，請稍後再試"}

        return {"url": img_url, "text": text_content, "theme": theme}

    except Exception as e:
        print(f"[Image Error] {e}")
        return {"error": f"生成圖片時發生錯誤：{str(e)}"}


def generate_custom_image(prompt: str) -> dict:
    """根據自訂 prompt 生成圖片"""
    if not GEMINI_API_KEY:
        return {"error": "Gemini API 尚未設定"}

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        response = model.generate_content(
            prompt,
            generation_config=types.GenerationConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        image_data = None
        text_content = ""

        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_data = part.inline_data.data
            elif hasattr(part, "text") and part.text:
                text_content = part.text.strip()

        if not image_data:
            return {"error": "Gemini 未能生成圖片，請稍後再試"}

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
            timeout=30,
        )
        if resp.status_code == 200 and resp.text.startswith("https://"):
            return resp.text.strip()
        print(f"[Catbox Error] status={resp.status_code} body={resp.text}")
        return None
    except Exception as e:
        print(f"[Catbox Upload Error] {e}")
        return None
