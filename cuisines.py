"""Shared cuisine options, search synonyms and conservative matching rules."""
import re

CUISINE_CATEGORIES = {
    "中餐 · 地方菜": ["川菜", "湘菜", "粤菜", "江浙菜", "云南菜", "东北菜", "西北菜", "京菜", "本帮菜", "潮汕菜"],
    "火锅 · 烧烤": ["火锅", "烧烤", "串串", "自助餐"],
    "面食 · 小吃": ["面馆", "小吃", "粥铺", "饺子"],
    "异国料理": ["西餐", "日料", "韩料", "东南亚菜", "意餐"],
    "轻食 · 饮品": ["咖啡", "甜品", "茶饮", "轻食"],
}
ALIASES = {
    "川菜": ["川菜", "四川菜", "川味", "川香"],
    "湘菜": ["湘菜", "湖南菜", "湘味"],
    "粤菜": ["粤菜", "广东菜", "粤式", "广式"],
    "江浙菜": ["江浙菜", "浙江菜", "江苏菜", "杭帮菜", "淮扬菜", "苏帮菜"],
    "云南菜": ["云南菜", "滇菜", "云南风味", "云贵菜"],
    "东北菜": ["东北菜", "东北风味"],
    "西北菜": ["西北菜", "西北风味", "陕西菜", "新疆菜"],
    "京菜": ["京菜", "北京菜", "京味菜", "北京烤鸭"],
    "本帮菜": ["本帮菜", "上海菜", "沪菜", "上海老饭店"],
    "潮汕菜": ["潮汕菜", "潮州菜", "潮菜"],
    "火锅": ["火锅", "火鍋", "hotpot", "hot pot", "涮肉", "涮羊肉"],
    "烧烤": ["烧烤", "烤肉", "bbq", "barbecue"],
    "串串": ["串串", "串串香"],
    "自助餐": ["自助餐", "自助", "buffet"],
    "面馆": ["面馆", "面食", "拉面", "面店"],
    "小吃": ["小吃", "生煎", "小笼包"],
    "粥铺": ["粥铺", "粥店", "砂锅粥"],
    "饺子": ["饺子", "水饺", "饺子馆"],
    "西餐": ["西餐", "意大利菜", "意式", "法餐", "法国菜", "牛排馆", "italian", "bistro"],
    "日料": ["日料", "日本料理", "日本菜", "日式", "寿司", "居酒屋"],
    "韩料": ["韩料", "韩国料理", "韩国菜", "韩式"],
    "东南亚菜": ["东南亚菜", "泰国菜", "泰式", "越南菜", "新加坡菜", "马来菜"],
    "意餐": ["意餐", "意大利菜", "意大利餐", "意式", "italian", "trattoria", "osteria", "pizzeria"],
    "咖啡": ["咖啡", "coffee", "cafe", "café"],
    "甜品": ["甜品", "甜点", "蛋糕", "dessert"],
    "茶饮": ["茶饮", "奶茶", "茶馆"],
    "轻食": ["轻食", "沙拉", "salad"],
}
SEARCH_TERMS = {
    "意餐": ["意大利餐厅", "意式餐厅", "意大利菜"],
    "日料": ["日本料理", "日料"], "韩料": ["韩国料理", "韩料"],
    "云南菜": ["云南菜", "滇菜"], "本帮菜": ["本帮菜", "上海菜"],
}


def cuisine_queries(cuisines):
    return ["|".join(SEARCH_TERMS.get(c, [c])) for c in dict.fromkeys(cuisines)] or ["餐厅"]


def venue_text(venue):
    # Addresses are deliberately excluded: 云南南路 does not prove 云南菜.
    return " ".join([str(venue.get("name") or ""), *map(str, venue.get("tags") or [])]).casefold()


def _contains(text, word):
    if word.isascii():
        return re.search(r"(?<![a-z])" + re.escape(word.casefold()) + r"(?![a-z])", text) is not None
    return word in text


def matches_cuisine(venue, cuisines):
    if not cuisines:
        return True
    text = venue_text(venue)
    # A regional label must not silently opt the user into hotpot.
    hotpot_selected = any(c in ("火锅", "串串") for c in cuisines)
    if not hotpot_selected and any(_contains(text, w) for w in ALIASES["火锅"] + ["串串"]):
        return False
    return any(_contains(text, word) for c in cuisines for word in ALIASES.get(c, [c]))
