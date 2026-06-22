"""
匯率查詢模組 — 使用免費 API 取得即時匯率
資料來源：ExchangeRate-API (free tier, 無需 API Key)
"""

import requests

BASE_URL = "https://open.er-api.com/v6/latest"

CURRENCY_ALIASES = {
    "美金": "USD", "美元": "USD", "usd": "USD",
    "日幣": "JPY", "日圓": "JPY", "日元": "JPY", "jpy": "JPY",
    "歐元": "EUR", "eur": "EUR",
    "英鎊": "GBP", "gbp": "GBP",
    "韓元": "KRW", "韓幣": "KRW", "krw": "KRW",
    "人民幣": "CNY", "rmb": "CNY", "cny": "CNY",
    "港幣": "HKD", "港元": "HKD", "hkd": "HKD",
    "澳幣": "AUD", "澳元": "AUD", "aud": "AUD",
    "加幣": "CAD", "加元": "CAD", "cad": "CAD",
    "新加坡幣": "SGD", "星幣": "SGD", "sgd": "SGD",
    "泰銖": "THB", "泰幣": "THB", "thb": "THB",
    "越南盾": "VND", "vnd": "VND",
    "馬來幣": "MYR", "令吉": "MYR", "myr": "MYR",
    "菲律賓披索": "PHP", "php": "PHP",
    "印尼盾": "IDR", "idr": "IDR",
    "瑞士法郎": "CHF", "chf": "CHF",
    "紐幣": "NZD", "紐元": "NZD", "nzd": "NZD",
    "台幣": "TWD", "新台幣": "TWD", "twd": "TWD",
}

CURRENCY_NAMES = {
    "USD": "美元", "JPY": "日圓", "EUR": "歐元", "GBP": "英鎊",
    "KRW": "韓元", "CNY": "人民幣", "HKD": "港幣", "AUD": "澳幣",
    "CAD": "加幣", "SGD": "新加坡幣", "THB": "泰銖", "VND": "越南盾",
    "MYR": "馬來幣", "PHP": "菲律賓披索", "IDR": "印尼盾",
    "CHF": "瑞士法郎", "NZD": "紐幣", "TWD": "新台幣",
}

POPULAR = ["USD", "JPY", "EUR", "KRW", "CNY", "GBP", "AUD", "THB"]


def get_exchange_rate(currency_input: str = "", amount: float = 0) -> str:
    """查詢匯率，以台幣為基準"""
    currency_input = currency_input.strip().lower()

    if not currency_input:
        return _get_popular_rates()

    code = CURRENCY_ALIASES.get(currency_input, currency_input.upper())

    if code == "TWD":
        return "台幣就是台幣啦 😄 請指定其他幣別，例如「美金匯率」"

    try:
        resp = requests.get(f"{BASE_URL}/TWD", timeout=10)
        data = resp.json()

        if data.get("result") != "success":
            return "匯率資料暫時無法取得，請稍後再試。"

        rates = data.get("rates", {})
        if code not in rates:
            return f"找不到「{currency_input}」的匯率資料，請確認幣別名稱。"

        rate = rates[code]
        name = CURRENCY_NAMES.get(code, code)
        # rate = 1 TWD 換多少外幣，反過來就是 1 外幣 = 多少台幣
        twd_per_unit = 1 / rate

        lines = [f"💱 {name}（{code}）匯率", ""]
        lines.append(f"1 {code} ≈ {twd_per_unit:.2f} TWD")
        lines.append(f"1 TWD ≈ {rate:.4f} {code}")

        if amount > 0:
            converted = amount * twd_per_unit
            lines.append("")
            lines.append(f"💰 {amount:,.0f} {code} ≈ {converted:,.0f} TWD")

        update_time = data.get("time_last_update_utc", "")
        if update_time:
            lines.append(f"\n📅 更新時間：{update_time[:16]}")

        return "\n".join(lines)

    except Exception as e:
        print(f"[Exchange Error] {e}")
        return "抱歉，匯率資料暫時無法取得，請稍後再試。"


def _get_popular_rates() -> str:
    """列出常用幣別匯率"""
    try:
        resp = requests.get(f"{BASE_URL}/TWD", timeout=10)
        data = resp.json()

        if data.get("result") != "success":
            return "匯率資料暫時無法取得，請稍後再試。"

        rates = data.get("rates", {})
        lines = ["💱 常用匯率（對台幣）", ""]

        for code in POPULAR:
            if code in rates:
                rate = rates[code]
                twd_per_unit = 1 / rate
                name = CURRENCY_NAMES.get(code, code)
                lines.append(f"  {name}（{code}）：{twd_per_unit:.2f} TWD")

        update_time = data.get("time_last_update_utc", "")
        if update_time:
            lines.append(f"\n📅 更新時間：{update_time[:16]}")

        return "\n".join(lines)

    except Exception as e:
        print(f"[Exchange Error] {e}")
        return "抱歉，匯率資料暫時無法取得，請稍後再試。"
