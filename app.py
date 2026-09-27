"""
CoJu —— 年轻人聚会规划助手 (Streamlit MVP)
运行: streamlit run app.py  (或 python -m streamlit run app.py)
无需 API Key 也能跑 (自动进入离线演示模式)。
"""
import streamlit as st
import folium
from streamlit_folium import st_folium

import config
import amap
import scoring
import llm
from mock_data import SAMPLE_MEMBERS

st.set_page_config(page_title="CoJu 聚会规划助手", page_icon="🍽️", layout="wide")

# ---------- 顶部 ----------
st.title("🍽️ CoJu — 年轻人聚会规划助手")
st.caption("把「通勤公平·预算·评分·口味」变成透明可解释的推荐，几分钟出一个可执行的聚会方案。")

# 用户自填高德 Key (每个用户用自己的, 不填则离线演示)
with st.sidebar:
    user_key = st.text_input(
        "🔑 高德 API Key (可选)", value="", type="password",
        help="填入你自己的高德 Web服务 Key 即可使用真实地图数据；留空则用离线演示数据。免费申请: console.amap.com")
config.set_runtime_key(user_key)

mode_badge = "🟢 LIVE 高德实时" if not config.offline_mode() else "🟡 OFFLINE 离线演示(缓存数据)"
if config.offline_mode():
    st.info(f"当前数据模式：{mode_badge} ｜ 在左侧填入你的高德 Key 可切换真实数据模式")
else:
    st.success(f"当前数据模式：{mode_badge} ｜ 正在使用真实地图数据")

# ---------- 侧边栏: 输入 ----------
st.sidebar.header("① 输入聚会信息")
n_members = st.sidebar.number_input("聚会人数", min_value=2, max_value=8, value=len(SAMPLE_MEMBERS), step=1)
members = []
for i in range(int(n_members)):
    # 示例数据不够时, 用最后一个示例的坐标兜底(离线用); LIVE模式会按真实地址解析
    m = SAMPLE_MEMBERS[i] if i < len(SAMPLE_MEMBERS) else {
        "name": f"小{chr(65 + i)}", "location": "", "lnglat": SAMPLE_MEMBERS[-1]["lnglat"]
    }
    with st.sidebar.expander(f"成员 {i+1}", expanded=(i < 3)):
        name = st.text_input("昵称", m["name"], key=f"n{i}")
        loc = st.text_input("出发地/工作地", m["location"], key=f"l{i}")
        members.append({"name": name, "location": loc, "lnglat": m["lnglat"]})

city = st.sidebar.text_input("城市 (LIVE模式用于地址解析)", "上海")
budget = st.sidebar.number_input("人均预算 (元)", min_value=20, max_value=1000, value=90, step=10)
# 菜系分类选项 (按大类分组)
CUISINE_CATEGORIES = {
    "🥢 中餐-地方菜": ["川菜", "湘菜", "粤菜", "江浙菜", "云南菜", "东北菜", "西北菜", "京菜", "本帮菜", "潮汕菜"],
    "🍲 火锅烧烤": ["火锅", "烧烤", "串串", "自助餐"],
    "🍜 面食小吃": ["面馆", "小吃", "粥铺", "饺子"],
    "🌏 异国料理": ["西餐", "日料", "韩料", "东南亚菜", "意餐"],
    "☕ 轻食饮品": ["咖啡", "甜品", "茶饮", "轻食"],
}
_all_cuisines = [c for lst in CUISINE_CATEGORIES.values() for c in lst]
cuisine_sel = st.sidebar.multiselect(
    "菜系偏好 (可多选)", _all_cuisines, default=["云南菜"],
    help="按地方菜/火锅/异国料理等分类挑选，可多选")
with st.sidebar.expander("按分类浏览菜系", expanded=False):
    for _cat, _items in CUISINE_CATEGORIES.items():
        st.caption(f"{_cat}：{'、'.join(_items)}")

scene_sel = st.sidebar.multiselect(
    "场景偏好 (可多选)", ["聚会", "约会", "商务", "家庭", "安静", "热闹"], default=["聚会"])
custom_pref = st.sidebar.text_input("其他偏好 (可选, 逗号分隔)", "")

prefs = list(cuisine_sel) + list(scene_sel) + [x.strip() for x in custom_pref.split(",") if x.strip()]

st.sidebar.markdown("---")
st.sidebar.subheader("② 吃完去哪玩 (可多选)")
ENT_OPTIONS = ["桌游", "KTV", "按摩", "拼豆", "剧本杀", "密室"]
ent_selected = []
_cols = st.sidebar.columns(2)
for _i, _opt in enumerate(ENT_OPTIONS):
    if _cols[_i % 2].checkbox(_opt, key=f"ent_{_opt}"):
        ent_selected.append(_opt)

st.sidebar.markdown("---")
st.sidebar.subheader("③ 推荐偏好")
st.sidebar.caption("通勤公平始终是核心，在此基础上选一个你更看重的维度：")

# 预设权重方案 (通勤公平/通勤始终占主导, 用户选的维度加权突出)
PRIORITY_PRESETS = {
    "🍽️ 餐厅评分优先": {"fairness": 0.30, "commute": 0.15, "budget": 0.10, "rating": 0.35, "pref": 0.10},
    "💰 人均预算优先": {"fairness": 0.30, "commute": 0.15, "budget": 0.35, "rating": 0.10, "pref": 0.10},
    "❤️ 偏好匹配优先": {"fairness": 0.30, "commute": 0.15, "budget": 0.10, "rating": 0.10, "pref": 0.35},
    "⚖️ 均衡 (默认)":   {"fairness": 0.35, "commute": 0.20, "budget": 0.15, "rating": 0.20, "pref": 0.10},
}
priority = st.sidebar.radio("我最看重：", list(PRIORITY_PRESETS.keys()), index=3)
w = PRIORITY_PRESETS[priority]

with st.sidebar.expander("查看当前权重明细", expanded=False):
    st.write({k: round(v, 2) for k, v in w.items()})

go = st.sidebar.button("🚀 生成聚会方案", type="primary", use_container_width=True)

# ---------- 点击时: 计算并存入 session_state (关键: 结果不随页面重跑消失) ----------
if go:
    try:
        with st.spinner("正在调用地图数据、计算通勤公平性并打分…"):
            cuisines, _scenes = scoring.split_prefs(prefs)
            kw = cuisines[0] if cuisines else "餐厅"
            candidates, src = amap.build_candidates(members, city, kw)
            top = scoring.rank_candidates(candidates, budget, prefs, weights=w, top_n=3)
            plan_text = llm.generate_plan(top, members, budget, prefs)
            # 玩乐推荐: 为每家推荐餐厅各自搜"该餐厅周边"的玩乐 (一一对应)
            entertainment_by_venue = []
            if ent_selected and top:
                for cand in top:
                    _center = cand.get("venue_lnglat") or cand.get("center")
                    items = amap.search_entertainment(_center, ent_selected) if _center else []
                    entertainment_by_venue.append({
                        "venue": cand["venue"],
                        "neighborhood": cand["neighborhood"],
                        "items": items,
                    })
        st.session_state["result"] = {
            "top": top, "src": src, "plan": plan_text, "members": list(members),
            "entertainment_by_venue": entertainment_by_venue, "ent_types": list(ent_selected),
        }
    except Exception as e:
        st.session_state["result"] = None
        st.error(f"生成失败：{e}")
        st.exception(e)

# ---------- 渲染结果 (从 session_state 读, 页面重跑也不丢) ----------
res = st.session_state.get("result")
if res:
    top = res["top"]
    st.success(f"方案已生成（数据来源：{res['src']}）")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📋 推荐方案")
        st.markdown(res["plan"])

        st.subheader("🏆 Top 3 候选（可解释打分）")
        for i, d in enumerate(top, 1):
            fb = " ⚠️附近无匹配菜系(兜底)" if d.get("is_fallback") else ("" if not scoring.split_prefs(prefs)[0] else " ✅菜系匹配")
            with st.expander(f"#{i} {d['neighborhood']} · {d['venue']} — 总分 {d['total']}{fb}",
                             expanded=(i == 1)):
                st.write(f"通勤时间：{d['commute_times']}（差距 {d['commute_gap_min']} 分，"
                         f"平均 {d['avg_commute_min']} 分）")
                # 公交路径明细
                routes = d.get("commute_routes") or []
                if routes:
                    st.write("**🚇 各成员公交路径**")
                    for mi, rt in enumerate(routes):
                        mname = res["members"][mi]["name"] if mi < len(res["members"]) else f"成员{mi+1}"
                        mode = rt.get("mode", "")
                        mins = rt.get("minutes")
                        steps = " → ".join(rt.get("steps", [])) or "—"
                        st.markdown(f"<span style='font-size:13px'>**{mname}**（{mode} {mins}分）："
                                    f"{steps}</span>", unsafe_allow_html=True)
                sc = d["scores"]
                st.write("**各维度得分**")
                st.progress(sc["fairness"], text=f"通勤公平性 {sc['fairness']}")
                st.progress(sc["commute"], text=f"平均通勤 {sc['commute']}")
                st.progress(sc["budget"], text=f"预算匹配 {sc['budget']}")
                st.progress(sc["rating"], text=f"场地评分 {sc['rating']}")
                st.progress(sc["pref"], text=f"偏好匹配 {sc['pref']}")

        # ---- 玩乐推荐 (按推荐餐厅分组, 每家餐厅显示"其周边"的玩乐) ----
        ebv = res.get("entertainment_by_venue") or []
        if res.get("ent_types"):
            st.subheader("🎉 吃完去哪玩（按餐厅就近推荐）")
            any_shown = False
            for grp in ebv:
                items = grp.get("items") or []
                if not items:
                    continue
                any_shown = True
                st.markdown(f"**🍽️ {grp['venue']} 周边**")
                for item in items:
                    rating = f"⭐{item['rating']}" if item.get("rating") else ""
                    hours = f"｜🕐{item['hours']}" if item.get("hours") else ""
                    st.markdown(f"　[{item['type']}] {item['name']} {rating}  \n"
                                f"　<span style='color:#888;font-size:13px'>{item.get('address','')} {hours}</span>",
                                unsafe_allow_html=True)
            if not any_shown:
                st.caption("推荐餐厅周边暂未找到所选玩乐项目，换个类型或扩大范围再试试。")

    with col2:
        st.subheader("🗺️ 地图")
        best = top[0]
        center = best.get("venue_lnglat") or best.get("center") or res["members"][0]["lnglat"]
        fmap = folium.Map(
            location=[center[1], center[0]], zoom_start=13, tiles=None
        )
        # 高德瓦片 (国内可访问, 无需key)
        folium.TileLayer(
            tiles="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
            attr="高德地图", subdomains=["1", "2", "3", "4"], name="高德",
        ).add_to(fmap)
        for m in res["members"]:
            folium.Marker([m["lnglat"][1], m["lnglat"][0]],
                          popup=f"{m['name']} 出发：{m['location']}",
                          icon=folium.Icon(color="blue", icon="user", prefix="fa")).add_to(fmap)
        folium.Marker([center[1], center[0]],
                      popup=f"集合点：{best['neighborhood']} · {best['venue']}",
                      icon=folium.Icon(color="red", icon="star", prefix="fa")).add_to(fmap)
        for m in res["members"]:
            folium.PolyLine([[m["lnglat"][1], m["lnglat"][0]], [center[1], center[0]]],
                            color="#c0392b", weight=2, opacity=0.6).add_to(fmap)
        # 玩乐点标注 (绿色) — 来自各餐厅周边
        for grp in (res.get("entertainment_by_venue") or []):
            for item in (grp.get("items") or []):
                if item.get("lnglat"):
                    folium.Marker([item["lnglat"][1], item["lnglat"][0]],
                                  popup=f"[{item['type']}] {item['name']}（{grp['venue']}周边）",
                                  icon=folium.Icon(color="green", icon="flag", prefix="fa")).add_to(fmap)
        st_folium(fmap, width=560, height=460, returned_objects=[])

    if config.offline_mode():
        st.caption("ℹ️ 当前为离线演示模式：使用预置的北京示例数据，与输入的具体地名无关。"
                   "填入 AMAP_KEY 后将根据真实地址实时计算。")
else:
    st.markdown(f"👈 在左侧填写 **{int(n_members)} 位成员的出发地、预算和偏好**，点击「生成聚会方案」。")
    st.markdown("> 💡 演示要点：切换左侧「推荐偏好」（餐厅评分/人均/偏好优先），观察推荐如何透明变化——"
                "背后是公开可调的权重方案，这就是 CoJu「非黑盒、可解释」的核心。")
