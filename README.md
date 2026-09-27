# CoJu — 年轻人聚会规划助手（MVP）

把「通勤公平 · 预算 · 评分 · 口味」变成**透明可解释**的加权推荐，几分钟给出可执行聚会方案。
Team RedBeanBun · MIB60001 生成式AI商业应用课程项目。

## 🚀 快速运行（5 分钟）

```bash
cd coju
pip install -r requirements.txt
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`。
**无需任何 API Key 即可运行** —— 默认进入「离线演示模式」，用缓存/模拟数据完整跑通全流程。

## 🔑 切换到高德实时数据（可选）

拿到高德开放平台 Key 后（https://console.amap.com/dev/key/app）：

```bash
# Mac/Linux
export AMAP_KEY=你的key
# Windows PowerShell
$env:AMAP_KEY="你的key"
streamlit run app.py
```

顶部徽章会从 🟡OFFLINE 变为 🟢LIVE。可选：设置 `LLM_API_KEY` 启用 LLM 生成更自然的方案文案（不设则用规则模板）。

## 🧱 架构（全 Python）

```
app.py        Streamlit 界面 + folium 地图 + 流程编排
llm.py        ① 自然语言解析参数  ④ 结构化结果 → 方案文案（均带规则兜底）
amap.py       ② 高德接入：WebAPI(主) → 离线mock(兜底)，统一 build_candidates()
scoring.py    ③ 可解释打分引擎 ★核心：通勤公平/平均通勤/预算/评分/偏好 加权
mock_data.py  离线演示数据（3成员 + 3商圈 + 餐厅 + 预缓存通勤）
config.py     Key 配置 + 离线模式开关
```

三层降级保证 demo 不翻车：**高德实时 → 缓存数据 → 全程离线**。

## 🎬 现场 Demo 脚本（约 3 分钟）

1. **讲痛点**（30s）：3个朋友散在城市各处，约饭群聊扯半天、有人通勤特别远 → 聚会告吹。
2. **输入**（30s）：左侧填 3 人出发地、预算 90、偏好「聚会,云南菜」，点「生成方案」。
3. **WOW 时刻**（60s）：结果推荐**三元桥**，强调「三人通勤差距仅 14 分钟」（呼应提案参考案例）。展开 Top1 看**各维度得分条**。
4. **可解释性**（40s）：拖动左侧「打分权重」滑块（如把公平性拉满），推荐**实时透明变化** —— 这就是我们相对「群聊」和「黑盒推荐」的核心差异。
5. **地图**（20s）：右侧地图展示 3 人起点 → 集合点的路线。

## 🛡️ 降级预案（Demo Day 必备）

| 层级 | 触发条件 | 操作 |
|---|---|---|
| 主 | 网络正常 + 有Key | 🟢 LIVE 高德实时 |
| 备1 | 断网 / Key限流 | 设 `COJU_OFFLINE=1` → 缓存数据，功能完整 |
| 备2 | 全挂 | 播放提前录好的 demo 走查视频 |

> 建议演示当天**默认用离线模式**（最稳），把「高德实时」作为加分展示——若现场网络好再切 LIVE。

## 🔭 提案里的 V2（demo 后再做）

保存偏好一键复用、朋友评分体系、多交通方式对比、真·高德 MCP 集成（当前 amap.py 已预留降级入口，可在此扩展 MCP client）。
