# 🤖 LINE 家庭助理 Bot

用自然語言管理家庭大小事的 LINE 機器人，支援**群組家庭助理**和 **1 對 1 個人助理**雙模式。  
搭配 Google Gemini API 理解中文口語，部署在雲端免費平台，每個群組／使用者資料獨立。

---

## 功能一覽

### 群組模式 — 家庭助理

| 功能 | 說明 |
|------|------|
| **行程管理** | 新增／查詢／修改／刪除行程，支援口語化日期（「下週三」「明天下午」） |
| **週期行程** | 支援每天、每週、每月重複（「每週三倒垃圾」「每月5號繳房租」） |
| **待辦事項** | 一次新增多筆、標記完成、查看清單 |
| **購物清單** | 獨立於待辦，支援新增／打勾／刪除／清空已購買 |
| **生日提醒** | 支援國曆與農曆，批次輸入，每日自動提醒壽星與近期生日 |
| **天氣查詢** | 中央氣象署 36 小時天氣預報，支援全台各縣市 |
| **匯率查詢** | 18 種常用幣別即時匯率，支援金額換算 |
| **旅遊行程規劃** | AI 規劃多天旅遊行程，自動存入行程表，支援偏好設定 |
| **每日推播** | 每天早上 7:30 自動推播當日行程＋天氣＋生日＋待辦＋購物摘要 |
| **自然語言** | 不用記指令，像跟人說話一樣 |
| **群組獨立** | 每個群組有自己的資料空間，加入多個群組互不干擾 |
| **行程歸檔** | 超過一年的行程自動歸檔，歷史搜尋仍可查到 |

### 1 對 1 模式 — 個人助理

| 功能 | 說明 |
|------|------|
| **智慧收藏** | 傳送網址、文字、圖片，AI 自動分類（待讀／待辦／靈感／帳務／工作／家庭／工具箱） |
| **網頁摘要** | 收藏網址時自動抓取內容、產生摘要和重點 |
| **圖片 OCR** | 傳送圖片自動辨識文字、偵測截止日和金額 |
| **收藏搜尋** | 語意搜尋收藏內容（Gemini 展開關鍵詞） |
| **寫作助手** | 代擬回覆稿，支援正式／輕鬆語氣 |
| **晚間摘要** | 每天晚上 9:00 自動推播當日收藏摘要 |
| **免觸發詞** | 不需要「小助理」前綴，直接傳訊息即可 |

> 💡 1 對 1 模式同時支援群組模式的行程、待辦、天氣等所有功能。

### UI 體驗

- **Quick Reply 快捷按鈕**：每次回覆下方顯示常用功能按鈕，一鍵操作
- **Flex Message 卡片**：收藏清單、行程、待辦、購物、總覽皆以卡片式呈現
- **收藏確認卡片**：收藏成功後顯示分類、摘要、重點、連結等資訊

---

## 設定步驟

### 第一步：申請 LINE Bot

1. 前往 [LINE Developers](https://developers.line.biz/)，用你的 LINE 帳號登入
2. 建立一個新的 **Provider**（名稱隨意，例如「我的家庭助理」）
3. 建立一個 **Messaging API Channel**
4. 在 Channel 設定頁面取得：
   - **Channel Secret**（Basic settings 頁籤）
   - **Channel Access Token**（Messaging API 頁籤，按 Issue 產生）
5. 關閉「Auto-reply messages」和「Greeting messages」（在 LINE Official Account Manager 裡）

### 第二步：取得 API Key

1. **Gemini API Key**：前往 [Google AI Studio](https://aistudio.google.com/apikey)，點選「Create API Key」
2. **中央氣象署 API Key**：前往 [CWA 開放資料平台](https://opendata.cwa.gov.tw/)，註冊後取得授權碼

> 💡 Gemini API 免費額度很大（每分鐘 15 次、每天 1500 次），家庭日常使用完全夠用。  
> 💡 匯率查詢使用 ExchangeRate-API 免費方案，無需額外申請 API Key。

### 第三步：部署到 Railway（推薦）

1. 把這個專案推上你的 GitHub Repository
2. 前往 [Railway](https://railway.com/)，用 GitHub 登入
3. 點選「New Project」→「Deploy from GitHub repo」→ 選擇這個 repo
4. 新增 PostgreSQL 資料庫（Add Plugin → PostgreSQL）
5. 在 Railway 專案的 **Variables** 頁面新增環境變數：

   ```
   LINE_CHANNEL_SECRET=你的Channel_Secret
   LINE_CHANNEL_ACCESS_TOKEN=你的Channel_Access_Token
   GEMINI_API_KEY=你的Gemini_API_Key
   CWA_API_KEY=你的氣象署API_Key
   ```

   > `DATABASE_URL` 由 Railway PostgreSQL 自動提供，不需手動設定。

6. Railway 會自動偵測 Python + Procfile 並部署
7. 部署完成後，在 **Settings → Networking** 取得你的公開網址，例如：  
   `https://你的專案名.up.railway.app`

### 第四步：設定 LINE Webhook

1. 回到 LINE Developers → 你的 Channel → Messaging API 頁籤
2. 在 **Webhook URL** 填入：  
   `https://你的專案名.up.railway.app/callback`
3. 開啟 **Use webhook**
4. 點選 **Verify** 確認連線成功（應顯示 Success）

### 第五步：開始使用

1. 用 LINE 掃描 Channel 的 QR Code 加 Bot 為好友
2. **1 對 1 模式**：直接傳訊息給 Bot 即可使用個人助理功能
3. **群組模式**：把 Bot 邀請到家庭群組，以「小助理」開頭發話

---

## 使用方式

### 群組模式

訊息以 **「小助理」** 或 **「/」** 開頭即可觸發：

#### 行程管理

```
小助理 下週三下午兩點看牙醫
小助理 每週三晚上八點倒垃圾
小助理 每月5號繳房租
小助理 這週有什麼行程？
小助理 看牙醫改到下週五
小助理 取消看牙醫
小助理 我哪天看過牙醫？（搜尋歷史行程）
```

#### 待辦事項

```
小助理 待辦：繳電話費、寄包裹
小助理 電話費繳了
小助理 待辦清單
```

#### 購物清單

```
小助理 要買牛奶、雞蛋、衛生紙
小助理 牛奶買了
小助理 購物清單
小助理 不用買衛生紙了
```

#### 生日提醒

```
小助理 媽媽生日是3月15號
小助理 阿嬤農曆九月初三生日
小助理 媽媽3月15號、爸爸8月20號、阿嬤農曆九月初三（批次輸入）
小助理 生日清單
```

#### 天氣 / 匯率

```
小助理 今天天氣如何
小助理 高雄天氣
小助理 美金匯率
小助理 100美金多少台幣
```

#### 旅遊規劃

```
小助理 幫我規劃花蓮三天兩夜
小助理 7/10出發去台南玩兩天
小助理 規劃墾丁三天，想玩水上活動
```

> 💡 規劃完成後會自動將每天行程存入行程表，方便後續查詢和推播提醒。

### 1 對 1 模式

不需要觸發詞，直接傳訊息：

#### 收藏管理

```
（直接貼網址）→ 自動收藏、分類、摘要
（直接傳圖片）→ 自動 OCR、分類、偵測截止日與金額
我的收藏
找一下停車費
修改收藏 5 會議記錄重點摘要
重新辨識（補辨識額度不足時的圖片）
```

#### 寫作助手

```
幫我回覆：老闆說週五要交報告
```

#### 行程 / 待辦 / 天氣

1 對 1 模式也支援所有群組功能，且不需要加「小助理」前綴。

---

## 自動推播

### 早上 7:30 — 群組＋個人

每天早上自動推播到所有使用中的群組和個人：

```
☀️ 早安！今天是 06/22（日）

🎂 今天是 媽媽 的生日！生日快樂！🎉
🎈 🌙阿嬤 的生日在 3 天後（9/3，國曆 10/15）

🌤️ 多雲  26~32°C  降雨 20%

📅 今日行程：
  • 2026-06-22 14:00  看牙醫

📋 待辦事項（2 項）
  ☐ 繳電話費
  ☐ 寄包裹

🛒 購物清單（3 項）
  ☐ 牛奶
  ☐ 雞蛋
  ☐ 衛生紙
```

### 晚上 9:00 — 個人收藏摘要

每天晚上推播給當天有收藏的 1 對 1 使用者：

```
📊 今日收藏摘要（共 3 筆）

📖 [待讀] React Server Components 深入解析
   介紹 RSC 的核心概念與實作方式
   🔗 https://example.com/article

💰 [帳務] 停車費收據
   金額：NT$120
   📷 有暫存圖片

💡 [靈感] 週末露營裝備清單
   帳篷、睡袋、營燈...

⚡ 其中 1 筆可能需要處理
💡 輸入「我的收藏」可查看完整清單
```

### 其他排程

| 排程 | 時間 | 說明 |
|------|------|------|
| 週期行程產生 | 每日 00:05 | 自動產生未來 7 天的週期行程實例 |
| 行程歸檔 | 每週日 03:00 | 歸檔超過一年的行程（歷史搜尋仍可查到） |

---

## 替代部署方式：Render

如果不想用 Railway，也可以用 [Render](https://render.com/)：

1. GitHub repo 連結到 Render
2. 建立 **Web Service**
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. 加入同樣的環境變數
6. Webhook URL 改成 Render 給的網址 + `/callback`

> ⚠️ Render 免費方案會在閒置 15 分鐘後休眠，第一次訊息可能會慢幾秒。Railway 免費方案目前比較穩定。

---

## 本機測試（可選）

```bash
# 安裝相依套件
pip install -r requirements.txt

# 設定環境變數
export LINE_CHANNEL_SECRET="你的secret"
export LINE_CHANNEL_ACCESS_TOKEN="你的token"
export GEMINI_API_KEY="你的key"
export CWA_API_KEY="你的氣象署key"
export DATABASE_URL="你的PostgreSQL連線字串"

# 啟動
python app.py

# 用 ngrok 建立公開通道（另開一個終端機）
ngrok http 8000
```

把 ngrok 產生的 https 網址 + `/callback` 填到 LINE Webhook URL。

---

## 專案結構

```
line-bot/
├── app.py                # 主程式：LINE webhook + 訊息處理 + 動作路由
├── database.py           # PostgreSQL 資料庫（行程／待辦／購物／生日／收藏）
├── gemini_handler.py     # Gemini API 意圖解析（21+ 種 action）+ 旅遊規劃 + 收藏分析
├── weather_handler.py    # 中央氣象署天氣預報
├── exchange_handler.py   # 匯率查詢（ExchangeRate-API）
├── scheduler.py          # APScheduler 排程（每日推播／晚間摘要／週期行程／行程歸檔）
├── line_ui.py            # LINE UI 模組（Quick Reply 快捷按鈕 + Flex Message 卡片）
├── requirements.txt      # Python 套件
├── Procfile              # 部署用啟動指令
└── README.md             # 本說明文件
```

---

## 技術架構

- **Flask** + **gunicorn**（Python 3.13）
- **LINE Messaging API v3 SDK**（Quick Reply + Flex Message）
- **Google Gemini API**（gemini-2.5-flash）— 自然語言意圖解析、收藏分析、圖片 OCR
- **PostgreSQL**（Railway 提供）
- **APScheduler** — 每日推播、晚間摘要、週期行程產生、行程歸檔
- **lunardate** — 農曆日期轉換
- **Jina Reader** — 網頁內容抓取（支援 JS 動態頁面）
- **中央氣象署 Open Data API** — 天氣預報
- **ExchangeRate-API** — 即時匯率（免費，無需 API Key）

---

## 費用

| 項目 | 費用 |
|------|------|
| LINE Messaging API | 免費（回覆無限制，主動推播每月 200 則） |
| Gemini API | 免費額度（每分鐘 15 次） |
| Railway | 免費方案提供每月 $5 USD 額度，此 Bot 通常用不到 $1 |
| 中央氣象署 API | 免費 |
| ExchangeRate-API | 免費 |
| Jina Reader API | 免費 |

> 💡 **推播額度說明**：向一個群組推一次算 1 則，與群組人數無關。早上推播 + 晚間摘要，1 個群組 + 1 個個人使用者 ≈ 每月約 60 則，200 則額度足夠日常使用。

**預估月費：$0** 🎉
