"""Transparent ranking of verified routes and strictly matched cuisines."""
from math import isfinite
from statistics import mean
from cuisines import ALIASES, matches_cuisine, venue_text

DEFAULT_WEIGHTS = {"fairness": .35, "commute": .20, "budget": .15, "rating": .20, "pref": .10}
SCORE_LABELS = {"fairness": "通勤公平性", "commute": "平均通勤", "budget": "预算匹配", "rating": "餐厅评分", "pref": "偏好匹配"}
PRIORITY_PRESETS = {
    "均衡": DEFAULT_WEIGHTS,
    "餐厅评分优先": {"fairness": .30, "commute": .15, "budget": .10, "rating": .35, "pref": .10},
    "人均预算优先": {"fairness": .30, "commute": .15, "budget": .35, "rating": .10, "pref": .10},
    "偏好匹配优先": {"fairness": .30, "commute": .15, "budget": .10, "rating": .10, "pref": .35},
}
_CUISINE_HINTS = ("菜", "火锅", "烧烤", "日料", "韩料", "西餐", "小吃", "面", "粥", "咖啡", "茶饮", "甜品", "自助", "串串", "料理", "意餐", "轻食", "饺")


def is_cuisine(term):
    return term in ALIASES or any(h in term for h in _CUISINE_HINTS)


def split_prefs(prefs):
    return ([p for p in prefs if is_cuisine(p)], [p for p in prefs if not is_cuisine(p)])


venue_matches_cuisine = matches_cuisine


def valid_times(times):
    return bool(times) and all(isinstance(t, (int, float)) and isfinite(t) and t >= 0 for t in times)


def fairness_score(times):
    if not valid_times(times):
        return 0.0
    longest = max(times)
    return 1.0 if longest == 0 else max(0.0, 1 - (longest-min(times))/longest)


def commute_score(times, cap_min=90):
    return max(0.0, 1 - mean(times)/cap_min) if valid_times(times) else 0.0


def budget_score(cost, budget, tolerance=.5):
    if cost is None or cost <= 0 or not budget:
        return .5
    # Budget is a target: the closer the per-person cost is to the target, the better.
    # Both overshooting and undershooting reduce the score symmetrically.
    return max(0.0, 1 - abs(cost - budget) / (budget * tolerance))


def rating_score(rating):
    return .5 if rating is None or rating <= 0 else max(0.0, min(1.0, rating/5))


def pref_score(venue, prefs):
    if not prefs:
        return .5
    hay = venue_text(venue)
    hits = [matches_cuisine(venue, [p]) if is_cuisine(p) else p.casefold() in hay for p in prefs]
    return sum(hits)/len(hits)


def rank_candidates(candidates, target_budget, user_prefs, weights=None, top_n=3, cuisine_terms=None):
    cuisines = split_prefs(user_prefs or [])[0] if cuisine_terms is None else cuisine_terms
    w = weights or DEFAULT_WEIGHTS
    if set(w) != set(DEFAULT_WEIGHTS) or any(not isfinite(v) or v < 0 for v in w.values()) or sum(w.values()) <= 0:
        raise ValueError("Invalid scoring weights")
    total_weight = sum(w.values())
    w = {k: v/total_weight for k, v in w.items()}
    scored, seen = [], set()
    for c in candidates:
        v, times = c["venue"], c["commute_times"]
        if not valid_times(times) or not matches_cuisine(v, cuisines):
            continue
        routes = c.get("commute_routes") or []
        if routes and (len(routes) != len(times) or any(r.get("minutes") != t for r, t in zip(routes, times))):
            continue
        ident = v.get("id") or (v["name"], tuple(v.get("lnglat") or c.get("center") or []))
        if ident in seen:
            continue
        seen.add(ident)
        parts = {"fairness": fairness_score(times), "commute": commute_score(times),
                 "budget": budget_score(v.get("cost"), target_budget), "rating": rating_score(v.get("rating")),
                 "pref": pref_score(v, user_prefs)}
        score = sum(w[k]*parts[k] for k in w)
        scored.append({
            "neighborhood": c["neighborhood"], "venue": v["name"], "venue_id": ident,
            "commute_times": times, "commute_gap_min": round(max(times)-min(times), 1),
            "avg_commute_min": round(mean(times), 1), "scores": {k: round(n, 3) for k, n in parts.items()},
            "weighted": {k: round(w[k]*parts[k], 3) for k in w}, "total": round(score, 3),
            "_sort_score": score, "cuisine_matched": True, "is_fallback": False,
            "commute_routes": routes, "center": c.get("center"), "venue_lnglat": v.get("lnglat"),
            "cost": v.get("cost"), "rating": v.get("rating"), "hours": v.get("hours") or "",
            "address": v.get("address") or "", "tags": v.get("tags") or [],
        })
    return sorted(scored, key=lambda d: d["_sort_score"], reverse=True)[:top_n]

