# LINE Bot 家庭助理 — 目前進度總結

## 已完成
- LINE Official Account 已建立（@720rqdly）
- Messaging API 已啟用，Channel Secret / Access Token 已取得
- Google Gemini API Key 已取得
- Railway 已部署，網址：web-production-2b79c.up.railway.app
- Webhook URL 已設定並 Verify 成功
- Bot 已能加入群組、接收觸發詞訊息、透過 Gemini 解析意圖

## Railway 環境變數（已設定）
- LINE_CHANNEL_SECRET
- LINE_CHANNEL_ACCESS_TOKEN
- GEMINI_API_KEY
- TZ=Asia/Taipei

## GitHub Repo
- 帳號：sorinalee
- Repo：line-bot（Public）
- Railway 會在每次 GitHub commit 後自動重新部署

## 本次修正內容（整合在 line-bot-final.zip 中）
1. line-bot-sdk 降版至 3.11.0（解決 Python 3.13 語法不相容）
2. 指定 Python 3.12.10（.python-version 檔案）
3. Gemini 模型改為 gemini-2.5-flash（解決 2.0-flash 配額問題）
4. 時區處理改為程式內建 UTC+8（不依賴環境變數）
5. 行程查詢加入日期過濾（修正「列出所有行程」的 bug）
6. Gemini system prompt 明確規定 days 最小值為 1（修正「今天行程查不到」的 bug）
7. 程式內也加了 days 的安全檢查（double protection）

## 待更新步驟
將 line-bot-final.zip 內的所有檔案上傳到 GitHub repo 覆蓋舊檔，Railway 會自動重新部署。

## 尚未實作的功能
- Google Calendar 同步（需串接 Google Calendar API + OAuth）
- 自動提醒推播（需加排程 + LINE Push Message）
- 觸發詞可自訂（改 app.py 第 72 行的 trigger_words）

## 費用狀態
- Railway Trial：30 天 / $5 免費額度（用完會停機，不會收費）
- Gemini API：免費額度（每分鐘 15 次、每天 1500 次）
- LINE Messaging API：回覆免費不限量
