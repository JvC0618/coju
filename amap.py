"""
高德地图接入层 —— 三层降级设计, 保证 demo 不翻车:
  路径A: 高德 MCP (体现"我们真的用了MCP", 答辩创新点) —— 预留扩展入口
  路径B: 高德 Web API 直调 (稳定, 生产级)  ← LIVE 主用
  路径C: 离线 mock 数据 (无Key/断网时, 100%可演示)

对外主入口:
  build_candidates(members, city)  → (候选列表, 数据来源标签)
    LIVE 模式: 地理编码每人地址 → 求几何中心 → 搜周边餐厅作候选 → 算每人通勤
    OFFLINE 模式: 直接用 mock_data 缓存
"""
import requests
import config
from mock_data import CANDIDATE_NEIGHBORHOODS

AMAP_BASE = "https://restapi.amap.com/v3"
AMAP_V5 = "https://restapi.amap.com/v5"


# ---------- 地理编码: 地址 → 坐标 + 城市编码 ----------
def geocode_full(address, city="上海"):
    """地址 → {'lnglat':[lng,lat], 'citycode':'021', 'adcode':'310000'}。失败 None。"""
    if config.offline_mode():
        return None
    try:
        r = requests.get(f"{AMAP_BASE}/geocode/geo", params={
            "key": config.get_amap_key(), "address": address, "city": city
        }, timeout=8)
        data = r.json()
        if data.get("geocodes"):
            g = data["geocodes"][0]
            lng, lat = g["location"].split(",")
            return {"lnglat": [float(lng), float(lat)],
                    "citycode": g.get("citycode") or "",
                    "adcode": g.get("adcode") or ""}
    except Exception as e:
        print("geocode error:", e)
    return None


def geocode(address, city="上海"):
    """兼容旧接口: 只返回 [lng, lat]。"""
    r = geocode_full(address, city)
    return r["lnglat"] if r else None


# ---------- 公交路径规划 ----------
def _parse_transit_segments(transit):
    """把一条 transit 方案解析成可读的换乘步骤列表, 如 ['步行820米','地铁10号线','步行300米']。"""
    steps = []
    for seg in transit.get("segments", []):
        # 步行
        walk = seg.get("walking", {})
        wd = walk.get("distance")
        if wd and int(float(wd)) > 50:
            steps.append(f"步行{int(float(wd))}米")
        # 公交/地铁
        bus = seg.get("bus", {})
        for line in bus.get("buslines", []):
            nm = line.get("name", "")
            if nm:
                steps.append(nm.split("(")[0])  # 去掉括号里的首末班信息
        # 地铁(部分版本在 railway/subway 字段)
        rail = seg.get("railway", {})
        if rail.get("name"):
            steps.append(rail["name"])
    return steps


def transit_plan(origin_lnglat, dest_lnglat, adcode="310000"):
    """
    公交路径规划。adcode: 城市行政区划代码(上海310000, 北京110000)。
    ⚠️ v5 接口的 city1/city2 要求 adcode(而非电话区号citycode) — 这是常见坑。
    返回 {'minutes':float, 'steps':[...], 'status':str, 'info':str} 或失败时 minutes=None。
    """
    if config.offline_mode():
        return {"minutes": None, "steps": [], "status": "offline", "info": "offline"}
    try:
        r = requests.get(f"{AMAP_V5}/direction/transit/integrated", params={
            "key": config.get_amap_key(),
            "origin": f"{origin_lnglat[0]},{origin_lnglat[1]}",
            "destination": f"{dest_lnglat[0]},{dest_lnglat[1]}",
            "city1": adcode or "310000", "city2": adcode or "310000",
            "show_fields": "cost",
        }, timeout=12)
        data = r.json()
        status, info = data.get("status"), data.get("info")
        trans = data.get("route", {}).get("transits")
        if trans:
            t0 = trans[0]
            # v5: 时长在 cost.duration; 老字段 duration 兜底
            dur = t0.get("cost", {}).get("duration") or t0.get("duration")
            mins = round(int(dur) / 60, 1) if dur else None
            return {"minutes": mins, "steps": _parse_transit_segments(t0),
                    "status": status, "info": info}
        return {"minutes": None, "steps": [], "status": status, "info": info}
    except Exception as e:
        print("transit error:", e)
        return {"minutes": None, "steps": [], "status": "exception", "info": str(e)}


def transit_minutes(origin_lnglat, dest_lnglat, adcode="310000"):
    """兼容接口: 只返回分钟数。"""
    return transit_plan(origin_lnglat, dest_lnglat, adcode).get("minutes")


def driving_minutes(origin_lnglat, dest_lnglat):
    """驾车通勤(分钟), 作为公交失败的兜底。失败返回 None。"""
    if config.offline_mode():
        return None
    try:
        r = requests.get(f"{AMAP_V5}/direction/driving", params={
            "key": config.get_amap_key(),
            "origin": f"{origin_lnglat[0]},{origin_lnglat[1]}",
            "destination": f"{dest_lnglat[0]},{dest_lnglat[1]}",
            "show_fields": "cost",
        }, timeout=10)
        data = r.json()
        paths = data.get("route", {}).get("paths")
        if paths:
            cost = paths[0].get("cost", {})
            if cost.get("duration"):
                return round(int(cost["duration"]) / 60, 1)
            # 老字段兜底
            if paths[0].get("duration"):
                return round(int(paths[0]["duration"]) / 60, 1)
    except Exception as e:
        print("driving error:", e)
    return None


def _haversine_km(a, b):
    """两经纬度点直线距离(km)。"""
    from math import radians, sin, cos, asin, sqrt
    lng1, lat1, lng2, lat2 = map(radians, [a[0], a[1], b[0], b[1]])
    dlng = lng2 - lng1; dlat = lat2 - lat1
    h = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlng/2)**2
    return 2 * 6371 * asin(sqrt(h))


def commute_detail(origin_lnglat, dest_lnglat, adcode="310000"):
    """
    稳健通勤, 三级兜底, 返回 {'minutes':float,'mode':str,'steps':[...]}:
      1. 公交 transit (含路径明细)  2. 驾车 driving  3. 直线距离估算
    """
    tp = transit_plan(origin_lnglat, dest_lnglat, adcode)
    if tp.get("minutes") is not None:
        return {"minutes": tp["minutes"], "mode": "公交", "steps": tp["steps"]}
    dv = driving_minutes(origin_lnglat, dest_lnglat)
    if dv is not None:
        return {"minutes": round(dv * 1.4, 1), "mode": "驾车估算", "steps": ["驾车路线"]}
    km = _haversine_km(origin_lnglat, dest_lnglat)
    return {"minutes": round(km / 18 * 60 + 5, 1), "mode": "直线估算", "steps": [f"直线约{round(km,1)}公里"]}


def commute_minutes(origin_lnglat, dest_lnglat, adcode="310000"):
    """兼容接口: 只返回分钟数。"""
    return commute_detail(origin_lnglat, dest_lnglat, adcode)["minutes"]


# ---------- 周边餐厅 POI ----------
def search_restaurants(center_lnglat, radius=3000, keyword="餐厅", limit=8):
    """商圈中心周边餐厅。返回 [{name,cost,rating,tags,hours,lnglat,address}, ...]。"""
    if config.offline_mode():
        return []
    try:
        r = requests.get(f"{AMAP_V5}/place/around", params={
            "key": config.get_amap_key(),
            "location": f"{center_lnglat[0]},{center_lnglat[1]}",
            "radius": radius, "keywords": keyword, "types": "050000",
            "page_size": limit, "show_fields": "business",
        }, timeout=10)
        data = r.json()
        out = []
        for p in data.get("pois", []):
            biz = p.get("business", {})
            loc = p.get("location", "").split(",")
            out.append({
                "name": p.get("name"),
                "cost": _to_float(biz.get("cost")),
                "rating": _to_float(biz.get("rating")),
                "tags": [p.get("type", "").split(";")[-1]] if p.get("type") else [],
                "hours": biz.get("opentime_today") or biz.get("opentime_week") or "",
                "address": p.get("address") or "",
                "lnglat": [float(loc[0]), float(loc[1])] if len(loc) == 2 else None,
            })
        return out
    except Exception as e:
        print("poi error:", e)
    return []


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------- 统一入口 ----------
def build_candidates(members, city="上海", cuisine_keyword="餐厅"):
    """
    members: [{name, location(地址文本), lnglat(离线用的示例坐标)}]
    返回 (候选列表, 来源标签)。
    """
    if config.offline_mode():
        from mock_data import build_offline_candidates
        return build_offline_candidates(), "OFFLINE(缓存/模拟数据)"

    # --- LIVE: 地理编码每位成员输入的真实地址 ---
    pts, adcode = [], "310000"
    for m in members:
        g = geocode_full(m["location"], city)
        if g:
            m["lnglat"] = g["lnglat"]   # 关键: 把真实坐标写回, 供地图/玩乐使用
            pts.append(g["lnglat"])
            if g.get("adcode"):
                adcode = g["adcode"][:4] + "00"  # 市级adcode (区县→市)
        else:
            pts.append(m.get("lnglat"))  # 编码失败回退示例坐标
    pts = [p for p in pts if p]
    if not pts:
        # 全部编码失败 → 回退离线
        from mock_data import build_offline_candidates
        return build_offline_candidates(), "OFFLINE(地址解析失败,回退缓存)"

    # 几何中心 → 周边餐厅作为候选集合点
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    kw = cuisine_keyword or "餐厅"
    venues = search_restaurants([cx, cy], radius=3000, keyword=kw, limit=10)
    # 若指定菜系但没搜到, 补搜通用"餐厅"作兜底候选
    if kw != "餐厅" and len(venues) < 3:
        venues += search_restaurants([cx, cy], radius=3000, keyword="餐厅", limit=6)

    if not venues:
        # POI 失败 → 回退预设商圈中心(仍算真实通勤)
        out = []
        for nb in CANDIDATE_NEIGHBORHOODS:
            details = [commute_detail(p, nb["center"], adcode) for p in pts]
            times = [d["minutes"] for d in details]
            for v in nb["venues"][:2]:
                out.append({"neighborhood": nb["neighborhood"], "center": nb["center"],
                            "commute_times": times, "commute_routes": details, "venue": v})
        return out, "LIVE(高德实时,POI回退预设)"

    out = []
    for v in venues:
        if not v.get("lnglat"):
            continue
        details = [commute_detail(p, v["lnglat"], adcode) for p in pts]
        times = [dd["minutes"] for dd in details]
        out.append({
            "neighborhood": v.get("address") or v.get("name"),
            "center": v["lnglat"],
            "commute_times": times,
            "commute_routes": details,
            "venue": v,
        })
    return out, "LIVE(高德实时)"


# ---------- 周边玩乐 POI (吃完去哪玩) ----------
# 玩乐类型 → 高德搜索关键词
ENTERTAIN_KEYWORDS = {
    "桌游": "桌游",
    "KTV": "KTV",
    "按摩": "按摩",
    "拼豆": "拼豆",
    "剧本杀": "剧本杀",
    "密室": "密室逃脱",
}


def search_entertainment(center_lnglat, types, radius=1000, per_type=2):
    """
    在集合点周边搜玩乐场所。
    types: 用户勾选的玩乐类型列表 (如 ["KTV","剧本杀"])。
    返回 [{type, name, rating, address, lnglat, hours}, ...]。
    离线模式返回 mock 数据。
    """
    if config.offline_mode():
        from mock_data import offline_entertainment
        return offline_entertainment(types)
    out = []
    for t in types:
        kw = ENTERTAIN_KEYWORDS.get(t, t)
        try:
            r = requests.get(f"{AMAP_V5}/place/around", params={
                "key": config.get_amap_key(),
                "location": f"{center_lnglat[0]},{center_lnglat[1]}",
                "radius": radius, "keywords": kw,
                "page_size": per_type, "show_fields": "business",
            }, timeout=10)
            data = r.json()
            for p in data.get("pois", []):
                biz = p.get("business", {})
                loc = p.get("location", "").split(",")
                out.append({
                    "type": t,
                    "name": p.get("name"),
                    "rating": _to_float(biz.get("rating")),
                    "address": p.get("address") or "",
                    "hours": biz.get("opentime_today") or "",
                    "lnglat": [float(loc[0]), float(loc[1])] if len(loc) == 2 else None,
                })
        except Exception as e:
            print("entertain error:", t, e)
    return out
