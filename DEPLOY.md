# CoJu 云端部署指南（Streamlit Community Cloud，免费）

部署后得到一个公开网址（如 `https://coju-redbeanbun.streamlit.app`），任何设备打开即用，无需安装。
默认离线模式，**不填任何 Key 就能完整演示**。

---

## 前置准备
- 一个 GitHub 账号（免费）
- coju 文件夹里的全部文件（app.py / scoring.py / amap.py / llm.py / mock_data.py / config.py / requirements.txt / README.md）

---

## 步骤一：把代码放上 GitHub

**方式A — 网页上传（最简单，不用装 git）**
1. 登录 https://github.com → 右上角 **+ → New repository**
2. Repository name 填 `coju`，选 **Public**（Streamlit 免费版要求公开），点 Create
3. 进入空仓库 → 点 **uploading an existing file**
4. 把 coju 文件夹里的**所有文件**拖进去 → 底部 **Commit changes**

**方式B — 命令行（会 git 的话）**
```bash
cd coju
git init && git add . && git commit -m "CoJu MVP"
git branch -M main
git remote add origin https://github.com/你的用户名/coju.git
git push -u origin main
```

---

## 步骤二：在 Streamlit Cloud 部署

1. 打开 https://share.streamlit.io → **Sign in with GitHub**（授权）
2. 点 **Create app** →  **Deploy a public app from GitHub**
3. 填写：
   - **Repository**：`你的用户名/coju`
   - **Branch**：`main`
   - **Main file path**：`app.py`
4. 点 **Deploy!**
5. 等 2–4 分钟（首次会自动 `pip install requirements.txt`），完成后自动打开你的公开网址 🎉

> 网址形如 `https://coju-xxxx.streamlit.app`，可在 App settings 里自定义子域名。

---

## 步骤三（可选）：填入 API Key 启用实时数据

不填也能演示（离线模式）。若已拿到高德 Key，想开 🟢LIVE：

1. 在 Streamlit Cloud 你的 app 页面 → 右下 **⋮ → Settings → Secrets**
2. 按 TOML 格式粘贴：
   ```toml
   AMAP_KEY = "你的高德key"
   # 可选：启用LLM生成更自然的文案
   LLM_API_KEY = "你的llm key"
   LLM_BASE_URL = "https://api.openai.com/v1"
   LLM_MODEL = "gpt-4o-mini"
   ```
3. Save → app 自动重启，顶部徽章变 🟢LIVE

---

## 常见问题

- **依赖装不上 / 报 pyarrow 等错**：Streamlit Cloud 用 Python 3.12，我们的依赖都兼容；若报错把 requirements.txt 里版本号去掉重试。
- **streamlit-folium 地图不显示**：刷新页面即可；云端首次加载前端组件略慢。
- **要私有仓库**：Streamlit 免费版仅支持公开仓库。项目无敏感信息，公开即可（Key 放 Secrets 不进代码）。
- **演示当天最稳做法**：默认离线模式演示（不依赖任何外部 API），LIVE 作为加分项。

---

## Demo Day 提示
把这个公开网址直接写进技术报告和 PPT，答辩时用**手机+电脑同时打开**证明"任何设备可用"，比本地 exe 更有说服力。
