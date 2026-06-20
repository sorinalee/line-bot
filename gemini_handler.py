"""
Gemini API 模組 — 解析使用者自然語言意圖
回傳結構化 JSON 供主程式執行動作
"""

import json
import google.generativeai as genai


SYSTEM_PROMPT = """你是一個 LINE 群組裡的家庭助理 Bot。你的工作是理解使用者的訊息，判斷他們想做什麼，然後回傳一個 JSON 物件。

## 你能處理的動作（action）

1. **add_event** — 新增行程
   回傳：{"action": "add_event", "data": {"title": "看牙醫", "date": "2025-07-05", "time": "14:00"}}
   
2. **query_events** — 查詢行程
   回傳：{"action": "query_events", "data": {"days": 7}}
   
3. **delete_event** — 刪除/取消行程
   回傳：{"action": "delete_event", "data": {"keyword": "牙醫"}}

4. **add_todo** — 新增待辦（支援一次多筆）
   回傳：{"action": "add_todo", "data": {"items": ["牛奶", "雞蛋", "衛生紙"]}}
   
5. **complete_todo** — 完成待辦
   回傳：{"action": "complete_todo", "data": {"keyword": "牛奶"}}

6. **query_todos** — 查看待辦清單
   回傳：{"action": "query_todos", "data": {}}

7. **delete_todo** — 刪除待辦
   回傳：{"action": "delete_todo", "data": {"keyword": "衛生紙"}}

8. **summary** — 總覽（行程+待辦）
   回傳：{"action": "summary", "data": {}}

9. **chat** — 一般閒聊或無法歸類
   回傳：{"action": "chat", "reply": "你的回覆內容"}

## 重要規則

- **只回傳 JSON**，不要有任何其他文字、markdown 或解釋
- 日期請轉成 YYYY-MM-DD 格式（根據「現在時間」推算「下週三」「明天」「這週六」等）
- 時間請轉成 HH:MM 格式（「下午三點」→ "15:00"，「早上九點半」→ "09:30"）
- 如果使用者一次提到多個待辦，請全部放在 items 陣列裡
- 「買了」「完成了」「搞定」「OK了」都是 complete_todo
- 「取消」「不去了」「刪掉行程」是 delete_event
- 「刪掉待辦」「不用買了」是 delete_todo
- 「今天有什麼事」「這週行程」是 query_events
- 「目前狀態」「總覽」是 summary
- 如果是 chat，reply 請用親切口語的繁體中文回覆，簡短就好
"""


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

            return json.loads(text)

        except json.JSONDecodeError:
            # Gemini 沒有回傳合法 JSON
            return {"action": "chat", "reply": text if text else "我沒聽懂，可以再說一次嗎？"}
        except Exception as e:
            print(f"[Gemini Error] {e}")
            return None
