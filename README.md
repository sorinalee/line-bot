# 🤖 LINE 家庭助理 Bot

用自然語言管理家庭大小事的 LINE 群組機器人。  
搭配 Google Gemini API 理解中文口語，部署在雲端免費平台，每個群組資料獨立。

---

## 功能一覽

| 功能 | 說明 |
|------|------|
| **行程管理** | 新增／查詢／刪除行程，支援口語化日期（「下週三」「明天下午」） |
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

### 第五步：加入群組

1. 用 LINE 掃描 Channel 的 QR Code 加 Bot 為好友
2. 把 Bot 邀請到群組
3. 開始使用！

---

## 使用方式

在群組中，訊息以 **「小助理」** 或 **「/」** 開頭即可觸發：

### 行程管理

```
小助理 下週三下午兩點看牙醫
小助理 每週三晚上八點倒垃圾
小助理 每月5號繳房租
小助理 這週有什麼行程？
小助理 取消看牙醫
小助理 我哪天看過牙醫？（搜尋歷史行程）
```

### 待辦事項

```
小助理 待辦：繳電話費、寄包裹
小助理 電話費繳了
小助理 待辦清單
```

### 購物清單

```
小助理 要買牛奶、雞蛋、衛生紙
小助理 牛奶買了
小助理 購物清單
小助理 不用買衛生紙了
```

### 生日提醒

```
小助理 媽媽生日是3月15號
小助理 阿嬤農曆九月初三生日
小助理 媽媽3月15號、爸爸8月20號、阿嬤農曆九月初三（批次輸入）
小助理 生日清單
```

### 天氣 / 匯率

```
小助理 今天天氣如何
小助理 高雄天氣
小助理 美金匯率
小助理 100美金多少台幣
```

### 旅遊規劃

```
小助理 幫我規劃花蓮三天兩夜
小助理 7/10出發去台南玩兩天
小助理 規劃墾丁三天，想玩水上活動
```

> 💡 規劃完成後會自動將每天行程存入行程表，方便後續查詢和推播提醒。

### 其他

```
小助理 目前狀態（總覽）
小助理 幫助
小助理 debug（查看資料庫原始資料）
```

---

## 每日自動推播

每天早上 **7:30**（台灣時間）自動推播到所有使用中的群組：

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
├── database.py           # PostgreSQL 資料庫（行程／待辦／購物清單／生日）
├── gemini_handler.py     # Gemini API 意圖解析（21 種 action）+ 旅遊規劃
├── weather_handler.py    # 中央氣象署天氣預報
├── exchange_handler.py   # 匯率查詢（ExchangeRate-API）
├── scheduler.py          # APScheduler 排程（每日推播／週期行程／行程歸檔）
├── requirements.txt      # Python 套件
├── Procfile              # 部署用啟動指令
└── README.md             # 本說明文件
```

---

## 技術架構

- **Flask** + **gunicorn**（Python 3.13）
- **LINE Messaging API v3 SDK**
- **Google Gemini API**（gemini-2.5-flash）— 自然語言意圖解析
- **PostgreSQL**（Railway 提供）
- **APScheduler** — 每日推播、週期行程產生、行程歸檔
- **lunardate** — 農曆日期轉換
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

> 💡 **推播額度說明**：向一個群組推一次算 1 則，與群組人數無關。1 個群組每日推播 = 每月約 30 則，200 則額度最多可支援 6 個群組。

**預估月費：$0** 🎉
