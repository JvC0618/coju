"""CoJu: a verifiable, same-city hangout planner."""
from copy import deepcopy
import hashlib
import html
import json

import folium
import streamlit as st
from streamlit_folium import st_folium

import amap
import config
import llm
import scoring
from cuisines import CUISINE_CATEGORIES
from mock_data import SAMPLE_MEMBERS

st.set_page_config(page_title="CoJu 聚会规划助手", page_icon="🍽️", layout="wide")
st.title("🍽️ CoJu · 年轻人聚会规划助手")
st.caption("一起出发，公平相聚。对比通勤、预算和口味，选择适合这次聚会的餐厅。")


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


with st.sidebar:
    mode = st.radio("数据模式", ["离线示例", "真实地点查询"], key="data_mode",
                    help="离线模式仅用于体验固定示例；真实地点查询需要高德 Web 服务 Key。",
                    disabled=config.FORCE_OFFLINE)
    user_key = st.text_input("高德 Web 服务 Key", type="password", key="amap_key",
                            help="仅在本次会话中使用，不写入源码或下载文件。", disabled=mode == "离线示例")
config.set_runtime_key(user_key)
demo = mode == "离线示例" or config.FORCE_OFFLINE
config.set_demo_mode(demo)
if demo:
    st.info("离线示例：使用固定的3位上海成员及模拟餐厅、通勤数据，仅供体验。真实地点请在左侧切换模式。")
else:
    st.info("真实地点查询：先核对各成员的出发地点，再查询高德数据。")
    if not config.get_amap_key():
        st.warning("请在左侧填写高德 Web 服务 Key，或由部署者配置 AMAP_KEY。")

with st.sidebar:
    st.header("① 聚会信息")
    members = []
    if demo:
        # 离线示例: 锁定 3 位上海成员, 不可增删
        for i in range(3):
            sample = SAMPLE_MEMBERS[i]
            with st.expander(f"成员 {i+1}", expanded=True):
                name = st.text_input("昵称", sample["name"], key=f"demo_name_{i}", disabled=True)
                address = st.text_input("出发地点", sample["location"], key=f"demo_loc_{i}", disabled=True,
                                        help="填写具体地铁站、建筑物或街道门牌号。")
                members.append({"name": name.strip() or f"成员{i+1}", "location": address.strip()})
    else:
        # 真实查询: 用 session_state 维护动态成员, 支持逐个增/删 (2-8人)
        if "live_members" not in st.session_state:
            st.session_state.live_members = [
                {"name": m["name"], "location": m["location"]} for m in SAMPLE_MEMBERS[:3]
            ]

        def _add_member():
            if len(st.session_state.live_members) < 8:
                n = len(st.session_state.live_members)
                st.session_state.live_members.append({"name": f"成员{n+1}", "location": ""})

        def _del_member(idx):
            if len(st.session_state.live_members) > 2:
                st.session_state.live_members.pop(idx)

        for i, m in enumerate(list(st.session_state.live_members)):
            with st.expander(f"成员 {i+1}：{m.get('name','')}", expanded=True):
                name = st.text_input("昵称", m["name"], key=f"live_name_{i}",
                                     help="填写具体地铁站、建筑物或街道门牌号。")
                address = st.text_input("出发地点", m["location"], key=f"live_loc_{i}")
                st.session_state.live_members[i]["name"] = name
                st.session_state.live_members[i]["location"] = address
                if len(st.session_state.live_members) > 2:
                    st.button("➖ 删除该成员", key=f"del_{i}", on_click=_del_member, args=(i,),
                              use_container_width=True)
                members.append({"name": name.strip() or f"成员{i+1}", "location": address.strip()})

        if len(st.session_state.live_members) < 8:
            st.button("➕ 添加成员", on_click=_add_member, use_container_width=True)
        else:
            st.caption("已达上限 8 位成员")
    city = st.text_input("城市", "上海", key="demo_city" if demo else "live_city", disabled=demo).strip()
    transport_label = st.selectbox("出行方式", list(amap.TRANSPORT_OPTIONS), key="demo_transport" if demo else "live_transport",
                                   disabled=demo,
                                   help="公共交通优先：无公交方案时，仅尝试短途步行或骑行。不会自动改为驾车。")
    transport = amap.TRANSPORT_OPTIONS[transport_label]
    budget = st.number_input("人均预算上限（元）", 20, 1000, 90, 10, key="budget")
    st.subheader("② 菜系与场景")
    categories = st.multiselect("先选菜系分类", list(CUISINE_CATEGORIES),
                                default=["中餐 · 地方菜"], key="cuisine_categories")
    cuisine_sel = []
    for cat in categories:
        with st.expander(cat, expanded=True):
            selected = st.multiselect("选择具体菜系", CUISINE_CATEGORIES[cat],
                                      default=["云南菜"] if cat == "中餐 · 地方菜" else [],
                                      key=f"cuisine_{list(CUISINE_CATEGORIES).index(cat)}")
            cuisine_sel.extend(selected)
    st.caption("多选表示任选一种；不选表示不限。仅推荐匹配的菜系，不用其他菜系凑数。")
    scenes = st.multiselect("场景偏好", ["聚会", "约会", "商务", "家庭", "安静", "热闹"],
                            default=["聚会"], key="scenes")
    st.caption("场景只按餐厅现有标签参与评分，不保证实际环境。")
    ent_types = st.multiselect("吃完想玩什么", list(amap.ENTERTAIN_KEYWORDS), key="ent_types")
    st.subheader("③ 推荐偏好")
    priority = st.radio("我更看重", list(scoring.PRIORITY_PRESETS), key="priority")
    weights = scoring.PRIORITY_PRESETS[priority]
    with st.expander("查看打分权重"):
        for metric, weight in weights.items():
            st.write(f"{scoring.SCORE_LABELS[metric]}：{weight:.0%}")
    st.caption("生成后切换推荐偏好，会重新排列本次已有候选。")
prefs = cuisine_sel + scenes

location_signature = digest({"members": members, "city": city, "demo": demo,
                             "key": hashlib.sha256(config.get_amap_key().encode()).hexdigest()})
resolved_members = deepcopy(members)
confirmed = demo
if not demo:
    st.subheader("核对出发地点")
    st.caption("核对名称和地址，避免重名地点或模糊地址影响计算。")
    if st.button("核对出发地点", key="resolve", disabled=not bool(config.get_amap_key())):
        st.session_state.pop("result", None)
        st.session_state.pop("location_options", None)
        try:
            options = []
            with st.spinner("正在查找出发地点…"):
                for i, m in enumerate(members, 1):
                    try:
                        options.append(amap.resolve_address_options(m["location"], city))
                    except amap.PlanningError as exc:
                        raise amap.PlanningError(f"成员{i}（{m['name']}）：{exc}") from None
            st.session_state["location_options"] = {"signature": location_signature, "options": options}
        except amap.PlanningError as exc:
            st.error(str(exc))
    found = st.session_state.get("location_options")
    if found and found["signature"] == location_signature:
        selected_locations = []
        for i, options in enumerate(found["options"]):
            chosen = st.selectbox(
                f"{members[i]['name']}的出发地点", range(len(options)),
                format_func=lambda idx, opts=options: f"{opts[idx]['name']} · {opts[idx]['formatted_address']}",
                index=None, placeholder="请选择并核对地点", key=f"place_{location_signature}_{i}")
            selected_locations.append(options[chosen] if chosen is not None else None)
        confirmation_id = digest(selected_locations)
        confirmed = st.checkbox("我已核对以上所有出发地点", key=f"confirmed_{confirmation_id}",
                                disabled=any(p is None for p in selected_locations))
        confirmed = confirmed and all(p is not None for p in selected_locations)
        if confirmed:
            for member, place in zip(resolved_members, selected_locations):
                member.update({**place, "name": member["name"], "resolved_name": place["name"],
                               "location": member["location"], "location_confirmed": True})
    else:
        st.caption("填写或修改出发地点后，点击“核对出发地点”。")

input_signature = digest({"locations": location_signature, "resolved": resolved_members, "confirmed": bool(confirmed),
                          "transport": transport, "budget": budget, "cuisines": cuisine_sel,
                          "scenes": scenes, "ent_types": ent_types})
res = st.session_state.get("result")
if res and res.get("signature") != input_signature:
    st.session_state.pop("result", None)
    res = None
    st.info("条件已修改，请重新生成方案。")

go = st.sidebar.button("🚀 生成聚会方案", type="primary", use_container_width=True,
                       disabled=not confirmed, key="generate")
if go:
    st.session_state.pop("result", None)
    try:
        with st.spinner("正在查询餐厅与路线，请稍候…"):
            candidates, source, diagnostics = amap.build_candidates(resolved_members, city, cuisine_sel, transport)
            st.session_state["result"] = {
                "signature": input_signature, "candidates": candidates, "source": source,
                "diagnostics": diagnostics, "members": deepcopy(resolved_members),
                "demo": demo, "entertainment": {}, "city": city, "transport": transport,
            }
    except amap.PlanningError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error("暂时无法生成方案，请重试；若仍失败，请将页面提示反馈给开发者。")
        print("CoJu generation failed:", type(exc).__name__)

res = st.session_state.get("result")
if res:
    top = scoring.rank_candidates(res["candidates"], budget, prefs, weights, cuisine_terms=cuisine_sel)
    diagnostics = res["diagnostics"]
    st.caption(f"搜索范围：{diagnostics['scope']}。本次搜索发现{diagnostics['matched']}家匹配餐厅；"
               f"最多核对12家附近候选的路线，不代表全城最优。")
    if diagnostics["route_missing"]:
        st.warning(f"{diagnostics['route_missing']}家候选未取得所有成员的可用路线，已排除；没有用驾车或直线估算代替。")
    if not top:
        if res["demo"]:
            st.warning("固定示例中没有符合所选菜系的餐厅。可换选云南菜、粤菜、火锅等示例菜系，或切换真实地点查询。")
        elif not diagnostics["matched"]:
            st.warning("本次搜索未找到菜系可核验的匹配餐厅；不代表该城市没有这种菜系。请调整选择后重试。")
        else:
            st.warning("找到了匹配餐厅，但没有候选取得所有成员的完整通勤路线。可更换出行方式或检查出发地点。")
    else:
        st.success(f"方案已生成 · {res['source']}")
        left, right = st.columns([1.1, 1])
        with left:
            st.subheader("推荐方案")
            st.markdown(llm.generate_plan(top, res["members"], budget, prefs))
            st.subheader(f"候选餐厅（{len(top)}家）")
            if len(top) < 3:
                st.caption("只展示已匹配且路线完整的候选，不足3家也不加入其他菜系。")
            for i, cand in enumerate(top, 1):
                matched_label = " · 菜系匹配" if cuisine_sel else ""
                with st.expander(f"#{i} {cand['venue']} · {cand['total']:.3f}{matched_label}", expanded=i == 1):
                    st.write(cand["address"] or cand["neighborhood"])
                    st.write(f"通勤差距 {cand['commute_gap_min']} 分钟 · 平均 {cand['avg_commute_min']} 分钟")
                    st.write("**各成员出行路线**" + ("（模拟示例）" if demo else ""))
                    downgraded = []
                    for member, route in zip(res["members"], cand["commute_routes"]):
                        st.write(f"{member['name']} · {route['mode']} · {route['minutes']}分钟")
                        st.caption(" → ".join(route["steps"]))
                        # 公共交通优先模式下, 记录实际未走公交(降级为步行/骑行)的成员
                        if res.get("transport") == "public_first" and route["mode"] in ("步行", "骑行"):
                            downgraded.append(f"{member['name']}（{route['mode']}）")
                    if downgraded:
                        st.warning("⚠️ 出行方式提示：你选择了「公共交通优先」，但以下成员附近暂无合适公交方案，"
                                   "已改用短途步行/骑行：" + "、".join(downgraded) + "。")
                    st.write("**各维度得分（0–1）**")
                    for metric, value in cand["scores"].items():
                        st.progress(value, text=f"{scoring.SCORE_LABELS[metric]} {value:.3f}")
                    st.caption("缺失人均或评分时，该项按中性分0.5处理；未公开的场景标签不计为匹配。")
                    if ent_types:
                        if demo:
                            st.caption("离线玩乐仅展示模拟项目，不表示这些地点真实位于该餐厅附近。")
                        cache_key = str(cand["venue_id"])
                        if go or st.button("查看这家餐厅附近的玩乐", key=f"ent_{digest(cache_key)}"):
                            try:
                                res["entertainment"][cache_key] = amap.search_entertainment(
                                    cand["venue_lnglat"] or cand["center"], ent_types, city=city)
                            except amap.PlanningError as exc:
                                st.warning(f"餐厅方案已保留；玩乐查询失败：{exc}")
                        if cache_key in res["entertainment"]:
                            items = res["entertainment"][cache_key]
                            if not items:
                                st.caption("本次未查到餐厅周边（约5公里内）的所选玩乐项目。")
                            for item in items:
                                st.write(f"{item['type']} · {item['name']}")
                                st.caption(("模拟项目" if demo else item.get("address") or "地址未提供"))
        with right:
            st.subheader("集合位置")
            map_index = st.selectbox("查看候选", range(len(top)),
                                     format_func=lambda i: top[i]["venue"], key=f"map_{digest([c['venue'] for c in top])}")
            best = top[map_index]
            center = best["venue_lnglat"] or best["center"]
            fmap = folium.Map(location=[center[1], center[0]], zoom_start=12, tiles=None)
            folium.TileLayer(
                tiles="https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
                attr="高德地图", subdomains=["1", "2", "3", "4"], name="高德").add_to(fmap)
            bounds = [[center[1], center[0]]]
            for member in res["members"]:
                point = member["lnglat"]
                latlng = [point[1], point[0]]
                bounds.append(latlng)
                popup = html.escape(f"{member['name']} · {member.get('resolved_name') or member['location']}")
                folium.Marker(latlng, popup=popup, icon=folium.Icon(color="blue", icon="user", prefix="fa")).add_to(fmap)
                folium.PolyLine([latlng, bounds[0]], color="#c0392b", dash_array="5,8", weight=2, opacity=.6).add_to(fmap)
            folium.Marker(bounds[0], popup=html.escape(best["venue"]),
                          icon=folium.Icon(color="red", icon="star", prefix="fa")).add_to(fmap)
            fmap.fit_bounds(bounds)
            st_folium(fmap, use_container_width=True, height=460, returned_objects=[], key=f"map_view_{digest([best['venue'], input_signature])}")
            st.caption("虚线仅连接出发点和集合点，不是实际道路线路。实际出行步骤见左侧。地图底图需要联网加载。")
else:
    st.markdown("在左侧设置预算和偏好，点击 **生成聚会方案**。")
    if not demo:
        st.caption("真实地点模式下，需先完成上方地点核对。")

