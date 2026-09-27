"""
离线演示数据 (OFFLINE 模式) —— 现场断网/无Key时的兜底。
以上海为例, 3个候选商圈 + 每个商圈的餐厅 + 预设的三人通勤时间。
真实模式下这些数据由 amap.py 从高德实时获取。
"""

# 三个示例用户 (工作地, 上海) —— 演示时可在界面里改
SAMPLE_MEMBERS = [
    {"name": "小A", "location": "五角场",   "lnglat": [121.514, 31.306]},
    {"name": "小B", "location": "陆家嘴",   "lnglat": [121.505, 31.245]},
    {"name": "小C", "location": "徐家汇",   "lnglat": [121.437, 31.195]},
]

# 候选商圈 (含中心坐标, 上海) + 每位成员到该商圈的通勤时间(分钟, 预缓存)
CANDIDATE_NEIGHBORHOODS = [
    {
        "neighborhood": "人民广场",
        "center": [121.475, 31.229],
        "commute_times": [32, 22, 28],   # 三人差距最小 → 最公平 (市中心)
        "venues": [
            {"name": "云海肴(人民广场店)", "cost": 90, "rating": 4.5,
             "tags": ["云南菜", "聚会", "环境好"], "hours": "10:00-22:00", "lnglat": [121.476, 31.230]},
            {"name": "小杨生煎(人广店)", "cost": 45, "rating": 4.3,
             "tags": ["上海小吃", "本帮菜"], "hours": "10:00-21:00", "lnglat": [121.474, 31.228]},
        ],
    },
    {
        "neighborhood": "静安寺",
        "center": [121.445, 31.224],
        "commute_times": [40, 30, 18],   # C近A远, 差距较大
        "venues": [
            {"name": "鹅夫人(静安店)", "cost": 120, "rating": 4.6,
             "tags": ["粤菜", "烧鹅", "聚会"], "hours": "10:30-22:00", "lnglat": [121.446, 31.225]},
            {"name": "海底捞(静安寺店)", "cost": 130, "rating": 4.7,
             "tags": ["火锅", "聚会", "热闹"], "hours": "10:00-次日6:00", "lnglat": [121.444, 31.223]},
        ],
    },
    {
        "neighborhood": "五角场",
        "center": [121.514, 31.306],
        "commute_times": [8, 42, 48],    # A很近, 差距大 → 不公平
        "venues": [
            {"name": "云南南路·五里关火锅(五角场店)", "cost": 95, "rating": 4.5,
             "tags": ["云南菜", "菌菇火锅", "聚会"], "hours": "11:00-22:00", "lnglat": [121.515, 31.307]},
            {"name": "巴厘龙虾(五角场店)", "cost": 110, "rating": 4.4,
             "tags": ["东南亚菜", "海鲜", "聚会"], "hours": "11:00-22:00", "lnglat": [121.513, 31.305]},
        ],
    },
]


# 离线示例公交路径 (按商圈, 上海地铁线路)
_OFFLINE_ROUTES = {
    "人民广场": [
        {"minutes": 32, "mode": "公交", "steps": ["步行400米", "地铁10号线", "步行300米"]},
        {"minutes": 22, "mode": "公交", "steps": ["步行500米", "地铁2号线", "步行250米"]},
        {"minutes": 28, "mode": "公交", "steps": ["步行350米", "地铁1号线", "步行300米"]},
    ],
    "静安寺": [
        {"minutes": 40, "mode": "公交", "steps": ["步行400米", "地铁10号线", "地铁2号线", "步行300米"]},
        {"minutes": 30, "mode": "公交", "steps": ["步行500米", "地铁2号线", "步行200米"]},
        {"minutes": 18, "mode": "公交", "steps": ["步行300米", "地铁1号线", "步行400米"]},
    ],
    "五角场": [
        {"minutes": 8, "mode": "公交", "steps": ["步行650米"]},
        {"minutes": 42, "mode": "公交", "steps": ["地铁2号线", "地铁10号线", "步行400米"]},
        {"minutes": 48, "mode": "公交", "steps": ["地铁1号线", "地铁10号线", "步行500米"]},
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


# ---------- 离线玩乐数据 (吃完去哪玩, 上海) ----------
_OFFLINE_ENTERTAIN = {
    "桌游": [
        {"name": "疯狂桌游吧(人广店)", "rating": 4.6, "address": "集合点商圈内", "hours": "13:00-次日2:00"},
        {"name": "骰子桌游俱乐部", "rating": 4.4, "address": "距集合点约400米", "hours": "14:00-24:00"},
    ],
    "KTV": [
        {"name": "温莎KTV(人广店)", "rating": 4.5, "address": "距集合点约300米", "hours": "12:00-次日2:00"},
        {"name": "纯K歌会所", "rating": 4.3, "address": "集合点商圈内", "hours": "12:00-次日3:00"},
    ],
    "按摩": [
        {"name": "良子健身按摩", "rating": 4.4, "address": "距集合点约500米", "hours": "11:00-次日1:00"},
        {"name": "富春山居采耳SPA", "rating": 4.5, "address": "集合点商圈内", "hours": "10:00-24:00"},
    ],
    "拼豆": [
        {"name": "手作时光·拼豆DIY", "rating": 4.7, "address": "距集合点约350米", "hours": "10:00-22:00"},
        {"name": "萌趣拼豆工坊", "rating": 4.5, "address": "集合点商圈内", "hours": "11:00-21:00"},
    ],
    "剧本杀": [
        {"name": "谜案馆剧本杀(人广店)", "rating": 4.8, "address": "距集合点约450米", "hours": "13:00-次日2:00"},
        {"name": "第六感沉浸剧本杀", "rating": 4.6, "address": "集合点商圈内", "hours": "12:00-24:00"},
    ],
    "密室": [
        {"name": "X-ROOM密室逃脱", "rating": 4.7, "address": "距集合点约500米", "hours": "13:00-24:00"},
        {"name": "惊魂密室(人广店)", "rating": 4.5, "address": "集合点商圈内", "hours": "12:00-23:00"},
    ],
}


def offline_entertainment(types):
    """离线模式: 返回勾选类型的玩乐推荐 (示例数据)。"""
    out = []
    for t in types:
        for item in _OFFLINE_ENTERTAIN.get(t, []):
            out.append({"type": t, "lnglat": None, **item})
    return out
