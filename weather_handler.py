"""
中央氣象署天氣預報模組
使用開放資料 API 取得 36 小時天氣預報
"""

import os
import requests

CWA_API_KEY = os.environ.get("CWA_API_KEY", "")
FORECAST_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"

CITY_ALIASES = {
    "台北": "臺北市", "臺北": "臺北市", "台北市": "臺北市",
    "新北": "新北市", "新北市": "新北市",
    "桃園": "桃園市", "桃園市": "桃園市",
    "台中": "臺中市", "臺中": "臺中市", "台中市": "臺中市",
    "台南": "臺南市", "臺南": "臺南市", "台南市": "臺南市",
    "高雄": "高雄市", "高雄市": "高雄市",
    "基隆": "基隆市", "基隆市": "基隆市",
    "新竹": "新竹市", "新竹市": "新竹市", "新竹縣": "新竹縣",
    "苗栗": "苗栗縣", "苗栗縣": "苗栗縣",
    "彰化": "彰化縣", "彰化縣": "彰化縣",
    "南投": "南投縣", "南投縣": "南投縣",
    "雲林": "雲林縣", "雲林縣": "雲林縣",
    "嘉義": "嘉義市", "嘉義市": "嘉義市", "嘉義縣": "嘉義縣",
    "屏東": "屏東縣", "屏東縣": "屏東縣",
    "宜蘭": "宜蘭縣", "宜蘭縣": "宜蘭縣",
    "花蓮": "花蓮縣", "花蓮縣": "花蓮縣",
    "台東": "臺東縣", "臺東": "臺東縣", "台東縣": "臺東縣",
    "澎湖": "澎湖縣", "澎湖縣": "澎湖縣",
    "金門": "金門縣", "金門縣": "金門縣",
    "連江": "連江縣", "連江縣": "連江縣", "馬祖": "連江縣",
}


def get_weather(location: str = "") -> str:
    if not CWA_API_KEY:
        return "天氣功能尚未設定，請設定 CWA_API_KEY 環境變數。"

    city = CITY_ALIASES.get(location.replace("市", "").replace("縣", ""), "")
    if not city:
        city = CITY_ALIASES.get(location, "")
    if not city and location:
        for alias, official in CITY_ALIASES.items():
            if alias in location or location in alias:
                city = official
                break
    if not city:
        city = "臺北市"

    try:
        resp = requests.get(FORECAST_URL, params={
            "Authorization": CWA_API_KEY,
            "locationName": city,
        }, timeout=10)
        data = resp.json()

        records = data.get("records", {})
        locations = records.get("location", [])
        if not locations:
            return f"查不到「{city}」的天氣資料"

        loc = locations[0]
        elements = {e["elementName"]: e for e in loc["weatherElement"]}

        lines = [f"🌤️ {city} 天氣預報", ""]

        time_periods = elements.get("Wx", {}).get("time", [])
        for period in time_periods:
            start = period["startTime"][5:16].replace("-", "/").replace("T", " ")
            end = period["endTime"][11:16]
            wx = period["parameter"]["parameterName"]

            pop_val = ""
            pop_periods = elements.get("PoP", {}).get("time", [])
            for pp in pop_periods:
                if pp["startTime"] == period["startTime"]:
                    pop_val = pp["parameter"]["parameterName"]
                    break

            min_t = ""
            max_t = ""
            min_periods = elements.get("MinT", {}).get("time", [])
            max_periods = elements.get("MaxT", {}).get("time", [])
            for mp in min_periods:
                if mp["startTime"] == period["startTime"]:
                    min_t = mp["parameter"]["parameterName"]
                    break
            for mp in max_periods:
                if mp["startTime"] == period["startTime"]:
                    max_t = mp["parameter"]["parameterName"]
                    break

            temp_str = f"{min_t}~{max_t}°C" if min_t and max_t else ""
            pop_str = f"降雨 {pop_val}%" if pop_val else ""

            detail = "  ".join(filter(None, [wx, temp_str, pop_str]))
            lines.append(f"📅 {start}~{end}")
            lines.append(f"   {detail}")
            lines.append("")

        return "\n".join(lines).strip()

    except Exception as e:
        print(f"[Weather Error] {e}")
        return "抱歉，天氣資料暫時無法取得，請稍後再試。"
