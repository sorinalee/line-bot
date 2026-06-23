"""
Gemini API 模組 — 解析使用者自然語言意圖
回傳結構化 JSON 供主程式執行動作
"""

import json
import google.generativeai as genai


SYSTEM_PROMPT = """你是一個 LINE 群組裡的家庭助理 Bot。你的工作是理解使用者的訊息，判斷他們想做什麼，然後回傳一個 JSON 物件。

## 你能處理的動作（action）

1. **add_event** — 新增行程（支援週期性）
   - 一般行程：{"action": "add_event", "data": {"title": "看牙醫", "date": "2025-07-05", "time": "14:00", "recurrence": ""}}
   - 每週重複：{"action": "add_event", "data": {"title": "倒垃圾", "date": "2025-07-02", "time": "20:00", "recurrence": "每週三"}}
   - 每週多天：{"action": "add_event", "data": {"title": "倒垃圾", "date": "2025-07-01", "time": "20:00", "recurrence": "每週一三五"}}
   - 每天重複：{"action": "add_event", "data": {"title": "吃藥", "date": "2025-07-01", "time": "08:00", "recurrence": "每天"}}
   - 每月重複：{"action": "add_event", "data": {"title": "繳房租", "date": "2025-07-05", "time": "", "recurrence": "每月5"}}
   注意：recurrence 只在使用者明確表示「每週」「每天」「每月」時才填寫。一般行程 recurrence 留空字串。

2. **query_events** — 查詢行程
   - 「今天有什麼事」→ {"action": "query_events", "data": {"days": 1, "target_date": ""}}
   - 「這週行程」→ {"action": "query_events", "data": {"days": 7, "target_date": ""}}
   - 「明天的行程」→ {"action": "query_events", "data": {"days": 2, "target_date": ""}}
   - 「未來三天」→ {"action": "query_events", "data": {"days": 3, "target_date": ""}}
   - 「6月30日的行程」→ {"action": "query_events", "data": {"days": 0, "target_date": "2026-06-30"}}
   - 「下週五有什麼事」→ {"action": "query_events", "data": {"days": 0, "target_date": "2026-06-27"}}
   注意：如果使用者問的是特定某一天，用 target_date（YYYY-MM-DD），days 設 0。如果問的是一段期間（「這週」「未來三天」），用 days，target_date 留空。days 最小值為 1，代表「今天」。

3. **search_events** — 搜尋歷史行程（查過去做過什麼、哪天去過哪裡）
   - 「我哪天看過牙醫？」→ {"action": "search_events", "data": {"keyword": "牙醫"}}
   - 「之前有去過健身房嗎？」→ {"action": "search_events", "data": {"keyword": "健身房"}}
   - 「上次買菜是什麼時候？」→ {"action": "search_events", "data": {"keyword": "買菜"}}

4. **delete_event** — 刪除/取消行程
   回傳：{"action": "delete_event", "data": {"keyword": "牙醫"}}

5. **update_event** — 修改/改期/延後行程（改日期、時間或標題）
   - 「看牙醫改到下週五」→ {"action": "update_event", "data": {"keyword": "牙醫", "new_date": "2026-06-27", "new_time": "", "new_title": ""}}
   - 「明天開會改成下午三點」→ {"action": "update_event", "data": {"keyword": "開會", "new_date": "", "new_time": "15:00", "new_title": ""}}
   - 「把看牙醫改到六月30，時間不變」→ {"action": "update_event", "data": {"keyword": "牙醫", "new_date": "2026-06-30", "new_time": "", "new_title": ""}}
   注意：只填要修改的欄位，不變的留空字串。keyword 是用來找到原行程的關鍵字。

6. **add_todo** — 新增待辦（支援一次多筆）
   回傳：{"action": "add_todo", "data": {"items": ["牛奶", "雞蛋", "衛生紙"]}}

7. **complete_todo** — 完成待辦
   回傳：{"action": "complete_todo", "data": {"keyword": "牛奶"}}

8. **query_todos** — 查看待辦清單
   回傳：{"action": "query_todos", "data": {}}

9. **delete_todo** — 刪除待辦
   回傳：{"action": "delete_todo", "data": {"keyword": "衛生紙"}}

10. **query_weather** — 查詢天氣
   - 「今天天氣如何」→ {"action": "query_weather", "data": {"location": "臺北"}}
   - 「高雄天氣」→ {"action": "query_weather", "data": {"location": "高雄"}}
   - 「會下雨嗎」→ {"action": "query_weather", "data": {"location": ""}}
   注意：如果使用者沒指定地點，location 留空字串。

11. **summary** — 總覽（行程+待辦+購物清單）
    回傳：{"action": "summary", "data": {}}

12. **add_shopping** — 新增購物清單（支援一次多筆）
    - 「要買牛奶」→ {"action": "add_shopping", "data": {"items": ["牛奶"]}}
    - 「購物清單加洗衣精、垃圾袋」→ {"action": "add_shopping", "data": {"items": ["洗衣精", "垃圾袋"]}}

13. **complete_shopping** — 購物清單打勾（已購買）
    - 「牛奶買了」→ {"action": "complete_shopping", "data": {"keyword": "牛奶"}}

14. **query_shopping** — 查看購物清單
    回傳：{"action": "query_shopping", "data": {}}

15. **delete_shopping** — 刪除購物清單項目
    - 「不用買牛奶了」→ {"action": "delete_shopping", "data": {"keyword": "牛奶"}}

16. **clear_shopping** — 清空已購買項目
    - 「清空購物清單」→ {"action": "clear_shopping", "data": {}}

17. **query_exchange** — 查詢匯率
    - 「美金匯率」→ {"action": "query_exchange", "data": {"currency": "美金", "amount": 0}}
    - 「日幣多少」→ {"action": "query_exchange", "data": {"currency": "日幣", "amount": 0}}
    - 「100美金多少台幣」→ {"action": "query_exchange", "data": {"currency": "美金", "amount": 100}}
    - 「匯率」→ {"action": "query_exchange", "data": {"currency": "", "amount": 0}}
    注意：如果沒指定幣別，currency 留空字串（會顯示常用匯率總覽）。amount 預設 0 表示只查匯率不換算。

18. **add_birthday** — 新增生日（支援國曆和農曆，支援一次多筆）
    - 單筆：「媽媽生日是3月15號」→ {"action": "add_birthday", "data": {"items": [{"name": "媽媽", "month": 3, "day": 15, "year": null, "is_lunar": false}]}}
    - 單筆農曆：「阿嬤農曆九月初三生日」→ {"action": "add_birthday", "data": {"items": [{"name": "阿嬤", "month": 9, "day": 3, "year": null, "is_lunar": true}]}}
    - 多筆：「媽媽3月15號、爸爸8月20號、阿嬤農曆九月初三」→ {"action": "add_birthday", "data": {"items": [{"name": "媽媽", "month": 3, "day": 15, "year": null, "is_lunar": false}, {"name": "爸爸", "month": 8, "day": 20, "year": null, "is_lunar": false}, {"name": "阿嬤", "month": 9, "day": 3, "year": null, "is_lunar": true}]}}
    注意：一律使用 items 陣列，即使只有一筆也放在陣列裡。year 可以是 null 或整數。month 和 day 必須是整數。
    **is_lunar 判斷規則**：每個人獨立判斷。提到「農曆」「舊曆」「陰曆」「初X」「正月」「臘月」時該筆 is_lunar 為 true，否則為 false。同一句話中可以混合國曆和農曆。
    農曆月份對照：正月=1、二月=2…臘月=12。日期對照：初一=1、初二=2…初十=10、十一=11…二十=20、廿一=21…三十=30。

19. **query_birthdays** — 查詢生日清單或近期生日
    - 「生日清單」→ {"action": "query_birthdays", "data": {}}
    - 「最近誰生日」→ {"action": "query_birthdays", "data": {}}

20. **delete_birthday** — 刪除生日
    - 「刪除媽媽的生日」→ {"action": "delete_birthday", "data": {"name": "媽媽"}}

21. **plan_trip** — 旅遊行程規劃（規劃完直接存入行程表）
    - 「幫我規劃三天兩夜花蓮行程，7/10出發」→ {"action": "plan_trip", "data": {"destination": "花蓮", "start_date": "2026-07-10", "days": 3, "preferences": ""}}
    - 「規劃東京五天自由行，8月1號到5號，想去迪士尼」→ {"action": "plan_trip", "data": {"destination": "東京", "start_date": "2026-08-01", "days": 5, "preferences": "想去迪士尼"}}
    - 「台南兩天一夜美食之旅，下週六出發」→ {"action": "plan_trip", "data": {"destination": "台南", "start_date": "2026-06-28", "days": 2, "preferences": "美食"}}
    注意：start_date 必須是 YYYY-MM-DD 格式。如果使用者沒有指定出發日期，start_date 留空字串 ""。
    preferences 放使用者提到的偏好（美食、親子、文青、購物等），沒有就留空字串。

22. **save_collection** — 使用者轉貼內容要你幫忙收藏（只在 1 對 1 中使用）
    - 當訊息是一段轉貼的文字、網址、或看起來是從別處複製過來的內容
    - 「幫我存這個」「記一下」+ 內容 → save_collection
    - 直接丟一個網址（https://...）→ save_collection
    回傳：{"action": "save_collection", "data": {"content": "使用者的原始內容"}}
    注意：如果使用者只是丟一段文字或網址，沒有明確要做其他事（不是新增行程、待辦等），在 1 對 1 模式下判斷為 save_collection

23. **query_collections** — 查看收藏清單
    - 「我的收藏」「今天收藏了什麼」→ {"action": "query_collections", "data": {"category": ""}}
    - 「看帳務的收藏」→ {"action": "query_collections", "data": {"category": "帳務"}}

24. **search_collections** — 搜尋收藏
    - 「找一下之前存的停車費」→ {"action": "search_collections", "data": {"keyword": "停車費"}}

25. **chat** — 一般閒聊或無法歸類
    回傳：{"action": "chat", "reply": "你的回覆內容"}

## 旅遊規劃 vs 一般聊天的判斷規則

- 使用者說「規劃行程」「安排旅遊」「幫我排行程」→ **plan_trip**
- 使用者只是問「台南有什麼好吃的」「東京推薦景點」→ **chat**（用知識直接回答）
- 關鍵差異：plan_trip 是要「產出多天行程並存入行程表」，chat 是單純問答

## 購物清單 vs 待辦事項的判斷規則

- 明確說「要買」「購物」「採買」「超市」「賣場」→ **add_shopping**
- 明確說「待辦」「要做」「記得」→ **add_todo**
- 模糊時（「加一下牛奶」）：如果是可購買的物品 → add_shopping；如果是要做的事 → add_todo
- 「XX買了」的判斷：先看購物清單有沒有 XX，有就是 complete_shopping；沒有則 complete_todo

## 重要規則

- **只回傳 JSON**，不要有任何其他文字、markdown 或解釋
- **日期必須是 YYYY-MM-DD 格式**，例如 "2026-06-22"，月和日必須補零（1月→01，5日→05）
- 根據「現在時間」推算相對日期（「今天」「明天」「下週三」「這週六」等），轉成 YYYY-MM-DD
- **絕對不要**回傳 "今天"、"明天"、"6/22"、"6月22日" 等非 YYYY-MM-DD 格式
- 時間請轉成 HH:MM 格式（「下午三點」→ "15:00"，「早上九點半」→ "09:30"）
- 如果沒有提到具體時間，time 欄位留空字串 ""
- 如果使用者一次提到多個待辦或購物項目，請全部放在 items 陣列裡
- 「買了」「完成了」「搞定」「OK了」都是 complete_todo 或 complete_shopping
- 「改到」「延後」「提前」「改時間」「改日期」「換到」是 update_event
- 「取消」「不去了」「刪掉行程」是 delete_event
- 「刪掉待辦」是 delete_todo
- 「不用買了」「取消購物」是 delete_shopping
- 「今天有什麼事」「這週行程」是 query_events
- 「哪天看過…」「上次…是什麼時候」「之前有沒有…」「有去過…嗎」是 search_events
- 「目前狀態」「總覽」是 summary
- add_event 支援新增過去日期的行程（例如「昨天去看了牙醫」→ 用昨天的日期）
- 查詢今天行程時 days 必須為 1，不可為 0
- 如果是 chat，reply 請用親切口語的繁體中文回覆，簡短就好
- 如果使用者問天氣、時事等你有能力回答的問題，用 chat 回覆即可
- 「我的收藏」「收藏清單」「今天收藏了什麼」是 query_collections
- 「找一下之前存的…」「有沒有關於…的收藏」是 search_collections
"""


COLLECTION_PROMPT = """你是一個個人助理，使用者轉貼了以下內容給你。
請分析內容並回傳 JSON：

{
  "category": "待讀/待辦/靈感/帳務/工作/家庭",
  "title": "簡短標題（10字以內）",
  "summary": "重點摘要（50字以內）",
  "has_deadline": true/false,
  "deadline_date": "YYYY-MM-DD 或空字串",
  "has_amount": true/false,
  "amount": "金額文字或空字串",
  "action_needed": "需要使用者做的事，沒有就空字串"
}

分類規則：
- 文章/新聞/教學連結 → 待讀
- 需要做的事、提醒 → 待辦
- 點子、想法、值得記住的 → 靈感
- 帳單、繳費、收據、發票 → 帳務
- 工作相關（會議、專案、公文） → 工作
- 家庭相關（學校、家務、親友） → 家庭
- 如果內容不明確，用「靈感」

只回傳 JSON，不要有其他文字。"""


IMAGE_ANALYSIS_PROMPT = """你是一個個人助理，使用者傳了一張圖片給你。
請仔細辨識圖片內容，回傳 JSON：

{
  "category": "待讀/待辦/靈感/帳務/工作/家庭",
  "title": "簡短標題（10字以內）",
  "summary": "重點摘要（50字以內）",
  "ocr_text": "圖片中辨識出的重要文字（日期、金額、聯絡方式等）",
  "has_deadline": true/false,
  "deadline_date": "YYYY-MM-DD 或空字串",
  "has_amount": true/false,
  "amount": "金額文字或空字串",
  "action_needed": "需要使用者做的事，沒有就空字串"
}

分類規則：
- 帳單、繳費單、收據、發票 → 帳務
- 會議白板、工作文件、公文 → 工作
- 名片 → 工作（摘要中列出姓名、電話、email）
- 學校通知、家庭文件 → 家庭
- 文章截圖 → 待讀
- 其他 → 靈感

只回傳 JSON，不要有其他文字。"""


class GeminiHandler:
    def __init__(self, api_key: str):
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=SYSTEM_PROMPT,
            )
        else:
            self.model = None

    def analyze_collection(self, text: str) -> dict:
        """分析轉貼的文字/網址內容，回傳分類和摘要"""
        if not self.model:
            return {"error": "Gemini API 尚未設定"}
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(f"{COLLECTION_PROMPT}\n\n內容：\n{text}")
            result_text = response.text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[-1]
            if result_text.endswith("```"):
                result_text = result_text.rsplit("```", 1)[0]
            return json.loads(result_text.strip())
        except Exception as e:
            print(f"[Gemini Collection Error] {type(e).__name__}: {e}")
            return {"category": "靈感", "title": text[:10], "summary": text[:50],
                    "has_deadline": False, "deadline_date": "",
                    "has_amount": False, "amount": "", "action_needed": ""}

    def analyze_image(self, image_bytes: bytes) -> dict:
        """分析圖片內容（OCR + 分類），回傳分類和摘要"""
        if not self.model:
            return {"error": "Gemini API 尚未設定"}
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            image_part = {"mime_type": "image/jpeg", "data": image_bytes}
            response = model.generate_content([IMAGE_ANALYSIS_PROMPT, image_part])
            result_text = response.text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[-1]
            if result_text.endswith("```"):
                result_text = result_text.rsplit("```", 1)[0]
            return json.loads(result_text.strip())
        except Exception as e:
            print(f"[Gemini Image Error] {type(e).__name__}: {e}")
            return {"category": "靈感", "title": "圖片", "summary": "無法辨識圖片內容",
                    "ocr_text": "", "has_deadline": False, "deadline_date": "",
                    "has_amount": False, "amount": "", "action_needed": ""}

    def plan_trip(self, destination: str, start_date: str, days: int,
                  preferences: str) -> dict:
        """讓 Gemini 規劃旅遊行程，回傳 {"data": [...]} 或 {"error": "..."}"""
        if not self.model:
            return {"error": "Gemini API 尚未設定"}

        pref_str = f"\n偏好：{preferences}" if preferences else ""

        prompt = f"""請幫我規劃一趟 {destination} {days} 天的旅遊行程。
出發日期：{start_date}{pref_str}

請回傳一個 JSON 陣列，每個元素代表一天的行程，格式如下：
[
  {{
    "date": "2026-07-10",
    "title": "花蓮第一天：太魯閣國家公園",
    "activities": [
      {{"time": "09:00", "activity": "太魯閣遊客中心"}},
      {{"time": "12:00", "activity": "午餐：原住民風味餐"}},
      {{"time": "14:00", "activity": "砂卡礑步道"}},
      {{"time": "18:00", "activity": "晚餐：花蓮市區美食"}}
    ]
  }}
]

規則：
- 每天 3-5 個活動，包含用餐
- title 格式為「目的地第N天：當日主題」
- time 格式為 HH:MM
- 只回傳 JSON 陣列，不要有其他文字
- 推薦當地特色景點和美食
- 行程要合理，考慮交通時間"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()
            return {"data": json.loads(text)}
        except json.JSONDecodeError as e:
            print(f"[Gemini Trip JSON Error] {e}\nRaw: {text[:500]}")
            return {"error": f"AI 回傳格式錯誤，請再試一次"}
        except Exception as e:
            print(f"[Gemini Trip Error] {type(e).__name__}: {e}")
            return {"error": f"{type(e).__name__}: {str(e)[:100]}"}

    def parse_intent(self, user_msg: str, context: str) -> dict | None:
        """解析使用者意圖，回傳結構化 dict，失敗回傳 None"""

        if not self.model:
            return {"action": "chat", "reply": "Gemini API 尚未設定，請設定 GEMINI_API_KEY 環境變數。"}

        prompt = f"""{context}

使用者說：「{user_msg}」

請回傳 JSON。"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # 清除可能的 markdown 包裹
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            result = json.loads(text)

            # 確保 query_events 的 days 至少為 1
            if result.get("action") == "query_events":
                days = result.get("data", {}).get("days", 7)
                if days < 1:
                    result["data"]["days"] = 1

            return result

        except json.JSONDecodeError:
            return {"action": "chat", "reply": text if text else "我沒聽懂，可以再說一次嗎？"}
        except Exception as e:
            print(f"[Gemini Error] type={type(e).__name__} msg={e}")
            return {"action": "chat", "reply": f"AI 暫時無法回應，請稍後再試（{type(e).__name__}）"}
