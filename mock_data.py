"""
离线演示数据 (OFFLINE 模式) —— 现场断网/无Key时的兜底。
以北京为例, 3个候选商圈 + 每个商圈的餐厅 + 预设的三人通勤时间。
真实模式下这些数据由 amap.py 从高德实时获取。
"""

# 三个示例用户 (工作地) —— 演示时可在界面里改
SAMPLE_MEMBERS = [
    {"name": "小A", "location": "望京SOHO",   "lnglat": [116.481, 39.996]},
    {"name": "小B", "location": "国贸CBD",     "lnglat": [116.457, 39.909]},
    {"name": "小C", "location": "中关村",       "lnglat": [116.316, 39.983]},
]

# 候选商圈 (含中心坐标) + 每位成员到该商圈的通勤时间(分钟, 预缓存)
CANDIDATE_NEIGHBORHOODS = [
    {
        "neighborhood": "三元桥",
        "center": [116.456, 39.966],
        "commute_times": [18, 22, 32],   # A/B/C, 差距最小 → 最公平
        "venues": [
            {"name": "云海肴(三元桥店)", "cost": 90, "rating": 4.5,
             "tags": ["云南菜", "聚会", "环境好"], "hours": "10:00-22:00", "lnglat": [116.454, 39.964]},
            {"name": "很久以前羊肉串", "cost": 110, "rating": 4.4,
             "tags": ["烧烤", "聚会", "热闹"], "hours": "11:00-次日2:00", "lnglat": [116.458, 39.967]},
        ],
    },
    {
        "neighborhood": "国贸",
        "center": [116.457, 39.909],
        "commute_times": [30, 5, 48],    # B很近但C很远, 差距大 → 不公平
        "venues": [
            {"name": "西贝莜面村(国贸店)", "cost": 100, "rating": 4.3,
             "tags": ["西北菜", "家常"], "hours": "10:00-22:00", "lnglat": [116.459, 39.910]},
            {"name": "鼎泰丰(国贸店)", "cost": 150, "rating": 4.6,
             "tags": ["江浙菜", "精致"], "hours": "11:00-21:30", "lnglat": [116.456, 39.908]},
        ],
    },
    {
        "neighborhood": "望京",
        "center": [116.470, 39.996],
        "commute_times": [8, 35, 40],    # A很近, 差距较大
        "venues": [
            {"name": "局气(望京店)", "cost": 85, "rating": 4.6,
             "tags": ["京菜", "聚会", "特色"], "hours": "10:30-22:00", "lnglat": [116.472, 39.997]},
            {"name": "四季民福烤鸭", "cost": 130, "rating": 4.7,
             "tags": ["烤鸭", "聚会"], "hours": "10:30-22:00", "lnglat": [116.468, 39.995]},
        ],
    },
]


# 离线示例公交路径 (按商圈)
_OFFLINE_ROUTES = {
    "三元桥": [
        {"minutes": 18, "mode": "公交", "steps": ["步行300米", "地铁10号线", "步行200米"]},
        {"minutes": 22, "mode": "公交", "steps": ["步行500米", "地铁2号线", "地铁10号线"]},
        {"minutes": 32, "mode": "公交", "steps": ["步行400米", "地铁4号线", "地铁10号线", "步行350米"]},
    ],
    "国贸": [
        {"minutes": 30, "mode": "公交", "steps": ["步行600米", "地铁1号线", "步行300米"]},
        {"minutes": 5, "mode": "公交", "steps": ["步行450米"]},
        {"minutes": 48, "mode": "公交", "steps": ["地铁13号线", "地铁1号线", "步行400米"]},
    ],
    "望京": [
        {"minutes": 8, "mode": "公交", "steps": ["步行650米"]},
        {"minutes": 35, "mode": "公交", "steps": ["地铁2号线", "地铁15号线", "步行300米"]},
        {"minutes": 40, "mode": "公交", "steps": ["地铁4号线", "地铁15号线", "步行500米"]},
    ],
}


def build_offline_candidates():
    """展开成 scoring.rank_candidates 需要的 (商圈×餐厅) 候选列表。"""
    out = []
    for nb in CANDIDATE_NEIGHBORHOODS:
        for v in nb["venues"]:
            out.append({
                "neighborhood": nb["neighborhood"],
                "center": nb["center"],
                "commute_times": nb["commute_times"],
                "commute_routes": _OFFLINE_ROUTES.get(nb["neighborhood"], []),
                "venue": v,
            })
    return out


# ---------- 离线玩乐数据 (吃完去哪玩) ----------
_OFFLINE_ENTERTAIN = {
    "桌游": [
        {"name": "疯狂桌游吧(三元桥店)", "rating": 4.6, "address": "三元桥商圈内", "hours": "13:00-次日2:00"},
        {"name": "骰子桌游俱乐部", "rating": 4.4, "address": "距集合点约400米", "hours": "14:00-24:00"},
    ],
    "KTV": [
        {"name": "温莎KTV(三元桥店)", "rating": 4.5, "address": "距集合点约300米", "hours": "12:00-次日2:00"},
        {"name": "纯K歌会所", "rating": 4.3, "address": "三元桥商圈内", "hours": "12:00-次日3:00"},
    ],
    "按摩": [
        {"name": "良子健身按摩", "rating": 4.4, "address": "距集合点约500米", "hours": "11:00-次日1:00"},
        {"name": "华夏良子(三元桥)", "rating": 4.5, "address": "三元桥商圈内", "hours": "10:00-24:00"},
    ],
    "拼豆": [
        {"name": "手作时光·拼豆DIY", "rating": 4.7, "address": "距集合点约350米", "hours": "10:00-22:00"},
        {"name": "萌趣拼豆工坊", "rating": 4.5, "address": "三元桥商圈内", "hours": "11:00-21:00"},
    ],
    "剧本杀": [
        {"name": "谜案馆剧本杀(三元桥店)", "rating": 4.8, "address": "距集合点约450米", "hours": "13:00-次日2:00"},
        {"name": "第六感沉浸剧本杀", "rating": 4.6, "address": "三元桥商圈内", "hours": "12:00-24:00"},
    ],
    "密室": [
        {"name": "X-ROOM密室逃脱", "rating": 4.7, "address": "距集合点约500米", "hours": "13:00-24:00"},
        {"name": "惊魂密室(三元桥店)", "rating": 4.5, "address": "三元桥商圈内", "hours": "12:00-23:00"},
    ],
}


def offline_entertainment(types):
    """离线模式: 返回勾选类型的玩乐推荐 (示例数据)。"""
    out = []
    for t in types:
        for item in _OFFLINE_ENTERTAIN.get(t, []):
            out.append({"type": t, "lnglat": None, **item})
    return out
