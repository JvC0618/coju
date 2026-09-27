"""
CoJu 可解释打分引擎 (核心卖点 — 非黑盒)
四个维度: 通勤公平性 / 预算匹配 / 场地评分 / 偏好匹配
菜系采用"强偏好+兜底": 匹配菜系的候选优先; 附近完全没有该菜系才用其他兜底并标注。
每个候选返回 total 分 + 分维度明细 (用于"为什么推荐这里"的解释)。
纯 Python, 无外部依赖, 可独立单元测试。
"""
from statistics import mean

# 可调权重 —— 可解释性的关键: 权重公开、可调, 不是黑盒
DEFAULT_WEIGHTS = {
    "fairness": 0.35,   # 通勤公平性 (灵魂指标)
    "commute": 0.20,    # 平均通勤 (越短越好)
    "budget": 0.15,     # 预算匹配
    "rating": 0.20,     # 场地评分
    "pref": 0.10,       # 口味/场景偏好匹配
}

# 菜系关键词判定 (用于区分"菜系词"和"场景词")
_CUISINE_HINTS = ("菜", "火锅", "烧烤", "日料", "韩料", "韩式", "西餐", "快餐",
                  "小吃", "面", "粉", "粥", "烤鸭", "海鲜", "咖啡", "茶", "甜品",
                  "自助", "牛肉", "串", "料理", "餐", "轻食", "饮", "饺")
_SCENE_WORDS = ("聚会", "约会", "商务", "家庭", "朋友", "热闹", "安静", "环境好", "精致")


def is_cuisine(term):
    """判断一个偏好词是否为菜系词 (而非场景词)。"""
    if term in _SCENE_WORDS:
        return False
    return any(h in term for h in _CUISINE_HINTS)


def split_prefs(prefs):
    """把偏好拆成 (菜系词列表, 场景词列表)。"""
    cuisines = [p for p in prefs if is_cuisine(p)]
    scenes = [p for p in prefs if not is_cuisine(p)]
    return cuisines, scenes


def venue_matches_cuisine(venue, cuisine_terms):
    """venue 是否匹配指定菜系 (检查名称 + 标签)。"""
    if not cuisine_terms:
        return True  # 未指定菜系 → 视为都匹配
    hay = (venue.get("name") or "") + " " + " ".join(venue.get("tags") or [])
    for c in cuisine_terms:
        # 云南菜 → 命中"云南"或"云南菜"; 去掉末尾"菜"再匹配一次, 提高召回
        core = c[:-1] if c.endswith("菜") and len(c) > 2 else c
        if c in hay or core in hay:
            return True
    return False


def fairness_score(commute_times):
    if not commute_times or max(commute_times) == 0:
        return 0.0
    spread = max(commute_times) - min(commute_times)
    return max(0.0, 1 - spread / max(commute_times))


def commute_score(commute_times, cap_min=90):
    if not commute_times:
        return 0.0
    return max(0.0, 1 - mean(commute_times) / cap_min)


def budget_score(venue_cost, target_budget, tolerance=0.5):
    if not target_budget or venue_cost is None:
        return 0.5
    diff = abs(venue_cost - target_budget) / (target_budget * tolerance)
    return max(0.0, 1 - diff)


def rating_score(venue_rating):
    if venue_rating is None:
        return 0.5
    return min(1.0, venue_rating / 5.0)


def pref_score(venue, user_prefs):
    """
    偏好匹配(软分): venue 的名称+标签 与全部偏好(菜系+场景)的重合度。
    用宽松匹配(去"菜"字), 与 venue_matches_cuisine 一致, 避免"菜系明明匹配却得0分"。
    """
    if not user_prefs:
        return 0.5
    if isinstance(venue, dict):
        hay = (venue.get("name") or "") + " " + " ".join(venue.get("tags") or [])
    else:
        hay = str(venue or "")
    hits = 0
    for p in user_prefs:
        core = p[:-1] if p.endswith("菜") and len(p) > 2 else p
        if p in hay or core in hay:
            hits += 1
    return hits / len(user_prefs)


def score_candidate(neighborhood, commute_times, venue, target_budget,
                    user_prefs, weights=None, cuisine_terms=None, commute_routes=None, center=None):
    w = weights or DEFAULT_WEIGHTS
    matched = venue_matches_cuisine(venue, cuisine_terms or [])
    parts = {
        "fairness": fairness_score(commute_times),
        "commute": commute_score(commute_times),
        "budget": budget_score(venue.get("cost"), target_budget),
        "rating": rating_score(venue.get("rating")),
        "pref": pref_score(venue, user_prefs),
    }
    total = sum(w[k] * parts[k] for k in w)
    detail = {
        "neighborhood": neighborhood,
        "venue": venue.get("name"),
        "commute_times": commute_times,
        "commute_gap_min": round(max(commute_times) - min(commute_times), 1) if commute_times else None,
        "avg_commute_min": round(mean(commute_times), 1) if commute_times else None,
        "scores": {k: round(v, 3) for k, v in parts.items()},
        "weighted": {k: round(w[k] * parts[k], 3) for k in w},
        "total": round(total, 3),
        "cuisine_matched": matched,
        "is_fallback": False,
        "commute_routes": commute_routes or [],
        "center": center,
        "venue_lnglat": venue.get("lnglat"),
    }
    return total, detail


def rank_candidates(candidates, target_budget, user_prefs, weights=None, top_n=3):
    """
    强偏好+兜底排序:
      1. 先按指定菜系过滤; 匹配的候选按总分降序 → 优先占据 Top-N
      2. 若匹配数量不足 top_n, 用"不匹配"的候选按总分补齐, 并标记 is_fallback=True
      3. 若完全没指定菜系, 退化为普通加权排序
    """
    cuisine_terms, _scenes = split_prefs(user_prefs or [])

    scored = []
    for c in candidates:
        _, detail = score_candidate(
            c["neighborhood"], c["commute_times"], c["venue"],
            target_budget, user_prefs, weights, cuisine_terms,
            c.get("commute_routes"), c.get("center")
        )
        scored.append(detail)

    if not cuisine_terms:
        scored.sort(key=lambda d: d["total"], reverse=True)
        return scored[:top_n]

    matched = [d for d in scored if d["cuisine_matched"]]
    unmatched = [d for d in scored if not d["cuisine_matched"]]
    matched.sort(key=lambda d: d["total"], reverse=True)
    unmatched.sort(key=lambda d: d["total"], reverse=True)

    result = matched[:top_n]
    if len(result) < top_n:
        for d in unmatched[: top_n - len(result)]:
            d["is_fallback"] = True   # 标注: 附近无匹配菜系, 兜底推荐
            result.append(d)
    return result


if __name__ == "__main__":
    demo = [
        {"neighborhood": "三元桥", "commute_times": [32, 40, 46],
         "venue": {"name": "云海肴", "cost": 90, "rating": 4.5, "tags": ["云南菜", "聚会"]}},
        {"neighborhood": "国贸", "commute_times": [20, 35, 70],
         "venue": {"name": "西贝莜面村", "cost": 100, "rating": 4.3, "tags": ["西北菜"]}},
        {"neighborhood": "望京", "commute_times": [50, 25, 30],
         "venue": {"name": "局气", "cost": 85, "rating": 4.6, "tags": ["京菜", "聚会"]}},
    ]
    print("== 指定 云南菜 ==")
    for i, d in enumerate(rank_candidates(demo, 90, ["聚会", "云南菜"]), 1):
        flag = " [兜底]" if d["is_fallback"] else ""
        print(f"#{i} {d['neighborhood']}·{d['venue']} 总分{d['total']} 菜系匹配={d['cuisine_matched']}{flag}")
    print("== 指定 日料(附近没有→兜底) ==")
    for i, d in enumerate(rank_candidates(demo, 90, ["日料"]), 1):
        flag = " [兜底]" if d["is_fallback"] else ""
        print(f"#{i} {d['neighborhood']}·{d['venue']} 总分{d['total']} 菜系匹配={d['cuisine_matched']}{flag}")
