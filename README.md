# MealTimeSupabase
MealTimeSupabase
7 月吃飯時間統計 App — Supabase 版
這是一個 Streamlit + Supabase PostgreSQL 的小型約時間 app。
功能：
7/1–7/31，每天午餐、晚餐可勾選
每個人用「姓名 + 編輯 PIN」修改自己的資料
PIN 會先做 SHA-256 hash，再存入資料庫，不存明碼
可刪除自己的資料
總覽頁顯示每個時段可出席人數與名單
自動排序最多人可出席的時間
本機 secrets
建立：
```text
.streamlit/secrets.toml
```
內容：
```toml
SUPABASE_URL = "https://klesmgvydjlgwpxxkart.supabase.co"
SUPABASE_KEY = "你的 Supabase publishable key 或 anon public key"
```
不要把 `.streamlit/secrets.toml` 上傳到 GitHub。
本機執行
```bash
pip install -r requirements.txt
streamlit run app.py
```
Streamlit Cloud 部署
上傳到 GitHub 的檔案：
app.py
requirements.txt
README.md
.gitignore
secrets.example.toml
不要上傳：
.streamlit/secrets.toml
到 Streamlit Cloud 的 App settings / Secrets 貼上：
```toml
SUPABASE_URL = "https://klesmgvydjlgwpxxkart.supabase.co"
SUPABASE_KEY = "你的 Supabase publishable key 或 anon public key"
```
注意事項
這是小型約飯工具，不是高安全性帳號系統。沒有正式登入機制，所以 RLS policy 是讓 app 能運作的簡化版本。
如果要更嚴謹，應改成：
Supabase Auth
每個使用者登入
RLS policy 綁定 auth.uid()
