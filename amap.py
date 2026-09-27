"""Amap Web APIs. Never replace failed live lookups with demo data or driving."""
from copy import deepcopy
from math import asin, cos, isfinite, radians, sin, sqrt
import re

import requests
import config
from cuisines import cuisine_queries, matches_cuisine

AMAP_BASE = "https://restapi.amap.com/v3"
AMAP_V5 = "https://restapi.amap.com/v5"
TRANSPORT_OPTIONS = {
    "公共交通优先（短途可步行 / 骑行）": "public_first",
    "仅公共交通": "transit", "步行": "walking", "骑行": "bicycling",
}


class PlanningError(ValueError):
    """A user-actionable validation or data availability problem."""


class MapServiceError(PlanningError):
    pass


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _dict(value):
    return value if isinstance(value, dict) else {}


def _to_float(value):
    try:
        n = float(value)
        return n if isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _point(value):
    parts = value.split(",") if isinstance(value, str) else value
    if not isinstance(parts, (list, tuple)) or len(parts) != 2:
        return None
    lng, lat = map(_to_float, parts)
    if lng is None or lat is None or not (-180 <= lng <= 180 and -90 <= lat <= 90):
        return None
    return [lng, lat]


def _coord(point):
    return f"{point[0]:.6f},{point[1]:.6f}"


def _request(path, params, *, version=5):
    if config.offline_mode():
        raise MapServiceError("当前为离线示例模式，请切换为真实地点查询。")
    try:
        response = requests.get(f"{AMAP_V5 if version == 5 else AMAP_BASE}/{path}",
                                params={**params, "key": config.get_amap_key()}, timeout=(4, 10))
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        # Error strings can contain request URLs and keys; never show or log them.
        raise MapServiceError("高德服务暂时无法连接，请检查网络后重试。") from None
    if not isinstance(data, dict) or str(data.get("status")) != "1":
        code = str(data.get("infocode", "")) if isinstance(data, dict) else ""
        if code in {"10001", "10005", "10006", "10007", "10009", "10012", "10013"}:
            message = "高德 Key 无效或接口权限不足，请检查 Web 服务 Key 的设置。"
        elif code in {"10003", "10004", "10010", "10014", "10019", "10020", "10021"}:
            message = "高德接口配额或调用频率受限，请稍后重试并检查配额。"
        else:
            message = "高德未能完成本次查询，请检查输入及接口配置后重试。"
        raise MapServiceError(message)
    return data


def _city_name(value):
    return _text(value).removesuffix("市")


def _same_city(item, city):
    actual = _text(item.get("cityname")) or _text(item.get("city")) or _text(item.get("province"))
    return bool(actual) and _city_name(actual) == _city_name(city)


def geocode_full(address, city="上海"):
    """Return only a unique, sufficiently precise geocode in the requested city."""
    data = _request("geocode/geo", {"address": address, "city": city}, version=3)
    valid = []
    precise = {"热点商圈", "道路", "道路交叉路口", "兴趣点", "门牌号", "单元号", "楼层", "房间"}
    for g in data.get("geocodes") or []:
        point = _point(g.get("location"))
        if not point or _text(g.get("level")) not in precise or not _same_city(g, city):
            continue
        valid.append({"lnglat": point, "citycode": _text(g.get("citycode")),
                      "adcode": _text(g.get("adcode")), "name": address,
                      "formatted_address": _text(g.get("formatted_address")),
                      "level": _text(g.get("level")), "city": city})
    return valid[0] if len(valid) == 1 else None


def _normalize(value):
    return re.sub(r"[\s\W_]+", "", value.casefold())


def resolve_address_options(address, city="上海"):
    """Offer verifiable places; ambiguous results require a user selection."""
    address, city = _text(address), _text(city)
    if len(address) < 2:
        raise PlanningError("请填写具体的地铁站、建筑物或街道门牌号，地点至少需要两个字。")
    if not city:
        raise PlanningError("请填写城市中文名，例如上海。")
    query = _normalize(address)
    city_normal = _normalize(city.removesuffix("市"))
    if query.startswith(city_normal):
        query = query[len(city_normal):].removeprefix("市")
    if len(query) < 2:
        raise PlanningError(f"「{address}」范围太大，请填写具体地点。")
    options = []
    g = geocode_full(address, city)
    if g and query in _normalize(g["formatted_address"]):
        options.append(g)
    data = _request("place/text", {"keywords": address, "region": city,
                                   "city_limit": "true", "page_size": 5})
    for p in data.get("pois") or []:
        point = _point(p.get("location"))
        formatted = "".join(_text(p.get(k)) for k in ("cityname", "adname", "address"))
        if not point or not _same_city(p, city) or query not in _normalize(_text(p.get("name")) + formatted):
            continue
        if any(_haversine_km(point, x["lnglat"]) < 0.03 for x in options):
            continue
        options.append({"id": _text(p.get("id")), "name": _text(p.get("name")),
                        "formatted_address": formatted, "lnglat": point,
                        "citycode": _text(p.get("citycode")), "adcode": _text(p.get("adcode")),
                        "level": "兴趣点", "city": city})
    if not options:
        raise PlanningError(f"无法可靠识别「{address}」。请补充区名、地铁站全名或街道门牌号；不会使用示例坐标代替。")
    return options


def _haversine_km(a, b):
    lng1, lat1, lng2, lat2 = map(radians, [a[0], a[1], b[0], b[1]])
    h = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lng2-lng1)/2)**2
    return 12742 * asin(sqrt(min(1, max(0, h))))


def _duration(path):
    raw = _dict(path.get("cost")).get("duration") or path.get("duration")
    seconds = _to_float(raw)
    return round(seconds / 60, 1) if seconds is not None and seconds > 0 else None


def _parse_transit_segments(transit):
    steps = []
    for seg in transit.get("segments") or []:
        walk = _dict(seg.get("walking"))
        distance = _to_float(walk.get("distance")) or 0
        if distance > 0:
            steps.append(f"步行{round(distance)}米")
        for line in _dict(seg.get("bus")).get("buslines") or []:
            name = _text(line.get("name"))
            if name:
                steps.append(name)
        rail = _dict(seg.get("railway"))
        if _text(rail.get("name")):
            steps.append(rail["name"])
    return steps


def transit_plan(origin, destination, citycode):
    if not citycode or len(citycode) > 4 or not citycode.isdigit():
        raise PlanningError("出发地点缺少有效的城市编码，请重新核对地点。")
    data = _request("direction/transit/integrated", {
        "origin": _coord(origin), "destination": _coord(destination),
        "city1": citycode, "city2": citycode, "show_fields": "cost", "strategy": "0",
    })
    for transit in _dict(data.get("route")).get("transits") or []:
        if any(_dict(s.get("taxi")) for s in transit.get("segments") or []):
            continue
        minutes = _duration(transit)
        steps = _parse_transit_segments(transit)
        if minutes is not None and steps:
            return {"minutes": minutes, "mode": "公共交通", "steps": steps}
    return None


def active_plan(origin, destination, mode):
    if mode not in {"walking", "bicycling"}:
        raise ValueError("Unsupported active transport mode")
    data = _request(f"direction/{mode}", {"origin": _coord(origin), "destination": _coord(destination),
                                         "show_fields": "cost"})
    for path in _dict(data.get("route")).get("paths") or []:
        minutes = _duration(path)
        steps = [_text(s.get("instruction")) for s in path.get("steps") or [] if _text(s.get("instruction"))]
        if minutes is not None and steps:
            return {"minutes": minutes, "mode": "步行" if mode == "walking" else "骑行", "steps": steps}
    return None


def commute_detail(origin, destination, citycode, transport="public_first"):
    if transport not in TRANSPORT_OPTIONS.values():
        raise PlanningError("请选择支持的出行方式。")
    distance = _haversine_km(origin, destination)
    if distance < 0.03:
        return {"minutes": 0.0, "mode": "步行", "steps": ["起终点坐标相距不足30米，请确认具体入口"], "nearby": True}
    if transport in {"walking", "bicycling"}:
        route = active_plan(origin, destination, transport)
    else:
        route = transit_plan(origin, destination, citycode)
        if route is None and transport == "public_first":
            if distance <= 2:
                route = active_plan(origin, destination, "walking")
                if route and route["minutes"] > 40:
                    route = None
            if route is None and distance <= 8:
                route = active_plan(origin, destination, "bicycling")
                if route and route["minutes"] > 45:
                    route = None
    return route or {"minutes": None, "mode": "未查到可用路线", "steps": []}


def _venue(p):
    business = _dict(p.get("business"))
    tags = re.split(r"[;,，；|]", _text(p.get("type")) + ";" + _text(business.get("tag")))
    return {"id": _text(p.get("id")), "name": _text(p.get("name")),
            "cost": _to_float(business.get("cost")), "rating": _to_float(business.get("rating")),
            "tags": [x for x in tags if x], "hours": _text(business.get("opentime_today")) or _text(business.get("opentime_week")),
            "address": _text(p.get("address")), "lnglat": _point(p.get("location")),
            "citycode": _text(p.get("citycode")), "cityname": _text(p.get("cityname")),
            "neighborhood": _text(business.get("business_area")) or _text(p.get("adname"))}


def search_restaurants(center, radius=3000, keyword="餐厅", limit=20, city="上海"):
    params = {"keywords": keyword, "types": "050000", "page_size": min(limit, 25),
              "show_fields": "business", "region": city, "city_limit": "true"}
    if center is None:
        path = "place/text"
    else:
        path = "place/around"
        params.update(location=_coord(center), radius=radius, sortrule="weight")
    return [_venue(p) for p in _request(path, params).get("pois") or [] if _same_city(p, city)]


def _validate_members(members, city):
    if not 2 <= len(members) <= 8:
        raise PlanningError("请填写2至8位成员。")
    for i, member in enumerate(members, 1):
        if not _text(member.get("location")):
            raise PlanningError(f"请填写成员{i}的出发地点。")
        if not member.get("location_confirmed") or not _point(member.get("lnglat")):
            raise PlanningError(f"请先核对成员{i}的真实出发地点。")
        if _city_name(member.get("city")) != _city_name(city):
            raise PlanningError("当前版本支持同城聚会，请核对所有成员所在城市。")
        code = _text(member.get("citycode"))
        if not code.isdigit() or len(code) > 4:
            raise PlanningError(f"成员{i}的城市编码无效，请重新核对地点。")


def build_candidates(members, city="上海", cuisines=None, transport="public_first"):
    """Return candidates, source and diagnostics; no silent fallbacks."""
    from mock_data import SAMPLE_MEMBERS, build_offline_candidates
    cuisines = [cuisines] if isinstance(cuisines, str) else list(cuisines or [])
    if config.offline_mode():
        if city != "上海" or [m.get("location") for m in members] != [m["location"] for m in SAMPLE_MEMBERS]:
            raise PlanningError("离线模式仅支持页面列出的3位上海示例成员；真实地点请切换查询模式。")
        if transport != "public_first":
            raise PlanningError("离线示例仅包含预置公共交通数据。")
        for member, sample in zip(members, SAMPLE_MEMBERS):
            member["lnglat"] = list(sample["lnglat"])
        candidates = [c for c in deepcopy(build_offline_candidates()) if matches_cuisine(c["venue"], cuisines)]
        return candidates, "离线模拟数据（上海固定示例）", {"searched": 6, "matched": len(candidates), "route_missing": 0,
                                                          "scope": "固定示例餐厅", "warnings": []}
    _validate_members(members, city)
    pts = [m["lnglat"] for m in members]
    center = [sum(p[i] for p in pts) / len(pts) for i in (0, 1)]
    queries = cuisine_queries(cuisines)
    seen, venues = set(), []

    def collect(search_center, radius):
        for query in queries:
            found = search_restaurants(search_center, radius, query, city=city)
            for v in found:
                ident = v.get("id") or (v["name"], tuple(v["lnglat"] or []))
                if ident in seen:
                    continue
                seen.add(ident)
                if v["lnglat"] and matches_cuisine(v, cuisines):
                    venues.append(v)

    scope = "集合中心周边3公里"
    collect(center, 3000)
    if len(venues) < 6:
        collect(center, 6000)
        scope = "集合中心周边6公里"
    if len(venues) < 3:
        collect(center, 10000)
        scope = "集合中心周边10公里"
    if len(venues) < 3:
        collect(None, 0)
        scope += "及同城关键词搜索"
    # A bounded nearby shortlist, not an exhaustive city-wide optimum.
    venues.sort(key=lambda v: _haversine_km(center, v["lnglat"]))
    shortlist = venues[:12]
    out, missing, route_cache = [], 0, {}
    for v in shortlist:
        details = []
        for m in members:
            key = (tuple(m["lnglat"]), tuple(v["lnglat"]), m["citycode"], transport)
            if key not in route_cache:
                route_cache[key] = commute_detail(m["lnglat"], v["lnglat"], m["citycode"], transport)
            details.append(route_cache[key])
        if any(d["minutes"] is None for d in details):
            missing += 1
            continue
        out.append({"neighborhood": v["neighborhood"] or v["address"] or v["name"], "center": v["lnglat"],
                    "commute_times": [d["minutes"] for d in details], "commute_routes": details, "venue": v})
    return out, "高德实时查询", {"searched": len(seen), "matched": len(venues), "evaluated": len(shortlist),
                                "route_missing": missing, "scope": scope, "warnings": []}


ENTERTAIN_KEYWORDS = {"桌游": "桌游", "KTV": "KTV", "按摩": "按摩", "拼豆": "拼豆", "剧本杀": "剧本杀", "密室": "密室逃脱"}


def search_entertainment(center, types, per_type=3, city="上海"):
    """集合点周边玩乐搜索。逐级扩大半径(1.5/3/5km)直到每类拿够;
    单个类型或单次请求失败不中断其他类型。"""
    if config.offline_mode():
        from mock_data import offline_entertainment
        return offline_entertainment(types)
    if center is None or not types:
        return []
    results = {t: [] for t in types}
    seen = set()

    def _collect(kind, search_radius):
        try:
            data = _request("place/around", {"location": _coord(center), "radius": search_radius,
                "keywords": ENTERTAIN_KEYWORDS.get(kind, kind), "page_size": 10,
                "sortrule": "weight", "show_fields": "business", "region": city, "city_limit": "true"})
        except MapServiceError:
            return
        for p in data.get("pois") or []:
            v = _venue(p)
            if not v["lnglat"] or not _same_city(p, city):
                continue
            if _haversine_km(center, v["lnglat"]) > search_radius / 1000 + 0.3:
                continue
            ident = v.get("id") or (v["name"], tuple(v["lnglat"]))
            if ident in seen:
                continue
            seen.add(ident)
            results[kind].append({**v, "type": kind,
                "distance_km": round(_haversine_km(center, v["lnglat"]), 2)})

    for search_radius in (1500, 3000, 5000):
        for kind in types:
            if len(results[kind]) < per_type:
                _collect(kind, search_radius)
        if all(len(results[t]) >= per_type for t in types):
            break

    out = []
    for kind in types:
        out.extend(sorted(results[kind], key=lambda x: x["distance_km"])[:per_type])
    return out

