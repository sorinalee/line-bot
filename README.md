# 🤖 LINE 家庭助理 Bot

用自然語言管理行程和待辦事項的 LINE 群組機器人。  
搭配 Google Gemini API 理解中文口語，部署在雲端免費平台。

---

## 功能一覽

- **行程管理**：新增 / 查詢 / 刪除行程，支援口語化日期（「下週三」「明天下午」）
- **待辦事項**：一次新增多筆、標記完成、查看清單
- **自然語言**：不用記指令，像跟人說話一樣
- **群組共用**：同一群組的成員共享行程和待辦

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

### 第二步：取得 Gemini API Key

1. 前往 [Google AI Studio](https://aistudio.google.com/apikey)
2. 點選「Create API Key」
3. 複製產生的 API Key

> 💡 Gemini API 免費額度很大（每分鐘 15 次、每天 1500 次），夫妻日常完全夠用。

### 第三步：部署到 Railway（推薦，最簡單）

1. 把這個專案推上你的 GitHub Repository
2. 前往 [Railway](https://railway.com/)，用 GitHub 登入
3. 點選「New Project」→「Deploy from GitHub repo」→ 選擇這個 repo
4. 在 Railway 專案的 **Variables** 頁面新增三個環境變數：

   ```
   LINE_CHANNEL_SECRET=你的Channel_Secret
   LINE_CHANNEL_ACCESS_TOKEN=你的Channel_Access_Token
   GEMINI_API_KEY=你的Gemini_API_Key
   ```

5. Railway 會自動偵測 Python + Procfile 並部署
6. 部署完成後，在 **Settings → Networking** 取得你的公開網址，例如：  
   `https://你的專案名.up.railway.app`

### 第四步：設定 LINE Webhook

1. 回到 LINE Developers → 你的 Channel → Messaging API 頁籤
2. 在 **Webhook URL** 填入：  
   `https://你的專案名.up.railway.app/callback`
3. 開啟 **Use webhook**
4. 點選 **Verify** 確認連線成功（應顯示 Success）

### 第五步：加入群組

1. 用 LINE 掃描 Channel 的 QR Code 加 Bot 為好友
2. 把 Bot 邀請到你和另一半的群組
3. 開始使用！

---

## 使用方式

在群組中，訊息以 **「小助理」** 或 **「/」** 開頭即可觸發：

```
小助理 下週三下午兩點看牙醫
小助理 這週有什麼行程？
小助理 取消看牙醫

小助理 要買牛奶、雞蛋、衛生紙
小助理 牛奶買了
小助理 待辦清單

小助理 目前狀態
小助理 幫助
```

也可以用斜線：

```
/週六晚上七點跟爸媽吃飯
/清單
```

---

## 替代部署方式：Render

如果不想用 Railway，也可以用 [Render](https://render.com/)：

1. GitHub repo 連結到 Render
2. 建立 **Web Service**
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. 加入同樣的三個環境變數
6. Webhook URL 改成 Render 給的網址 + `/callback`

> ⚠️ Render 免費方案會在閒置 15 分鐘後休眠，第一次訊息可能會慢幾秒。Railway 免費方案目前比較穩定。

---

## 本機測試（可選）

如果想在本機先測試：

```bash
# 安裝相依套件
pip install -r requirements.txt

# 設定環境變數
export LINE_CHANNEL_SECRET="你的secret"
export LINE_CHANNEL_ACCESS_TOKEN="你的token"
export GEMINI_API_KEY="你的key"

# 啟動
python app.py

# 用 ngrok 建立公開通道（另開一個終端機）
ngrok http 8000
```

把 ngrok 產生的 https 網址 + `/callback` 填到 LINE Webhook URL。

---

## 專案結構

```
line-bot-project/
├── app.py               # 主程式：LINE webhook + 訊息處理
├── database.py           # SQLite 資料庫（行程 + 待辦）
├── gemini_handler.py     # Gemini API 意圖解析
├── requirements.txt      # Python 套件
├── Procfile              # 部署用啟動指令
└── README.md             # 本說明文件
```

---

## 費用

- **LINE Messaging API**：免費（每月可發送 500 則主動推播，被動回覆不限）
- **Gemini API**：免費額度（每分鐘 15 次）
- **Railway**：免費方案提供每月 $5 USD 額度，這個 Bot 通常用不到 $1

**預估月費：$0** 🎉
