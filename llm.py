"""
LLM 层 —— 两个职责:
  parse_request(text)      自然语言 → 结构化参数 (JSON)
  generate_plan(top, ...)  结构化打分结果 → 自然语言方案

无 LLM_API_KEY 时自动用规则模板兜底, 保证不依赖外网也能完整 demo。
"""
import json
import config

try:
    from openai import OpenAI
    _HAS_SDK = True
except Exception:
    _HAS_SDK = False


def _client():
    if not _HAS_SDK or not config.LLM_API_KEY:
        return None
    return OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


def parse_request(text, fallback_members):
    """
    自然语言描述 → 结构化参数。
    返回 {members:[{name,location}], budget:int, prefs:[...], time:str}
    无 LLM 时返回 fallback (界面已有的表单值)。
    """
    cli = _client()
    if cli is None:
        return None  # 调用方改用表单值
    prompt = (
        "从下面这段聚会描述里抽取结构化参数, 只返回JSON, 字段: "
        "members(list of {name,location}), budget(人均预算,整数), "
        "prefs(口味/场景偏好 list), time(时间描述). 描述: " + text
    )
    try:
        resp = cli.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print("LLM parse error:", e)
        return None


def generate_plan(top_candidates, members, budget, prefs):
    """
    Top候选明细 → 自然语言方案。无 LLM 时用规则模板。
    """
    cli = _client()
    best = top_candidates[0]
    if cli is not None:
        prompt = (
            "你是聚会规划助手。基于以下打分结果, 用自然、友好的中文写一段聚会方案, "
            "包含: 推荐集合商圈及原因(强调通勤公平)、推荐餐厅(评分/人均/营业时间)、"
            "以及一句话备选。数据: " + json.dumps(top_candidates, ensure_ascii=False)
        )
        try:
            resp = cli.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print("LLM plan error:", e)

    # ---- 规则模板兜底 ----
    lines = []
    lines.append(f"🎯 推荐在 **{best['neighborhood']}** 集合。")
    if best.get("commute_gap_min") is not None:
        lines.append(
            f"这里对大家最公平——三人通勤时间差距仅约 {best['commute_gap_min']} 分钟"
            f"(平均 {best['avg_commute_min']} 分钟)。"
        )
    v = best["venue"]
    parts = [f"🍽️ 推荐餐厅:**{v}**"]
    lines.append("，".join(parts) + "。")
    lines.append(f"综合评分 {best['total']}（公平性 {best['scores']['fairness']}、"
                 f"评分 {best['scores']['rating']}、偏好匹配 {best['scores']['pref']}）。")
    if len(top_candidates) > 1:
        alt = top_candidates[1]
        lines.append(f"👉 备选:{alt['neighborhood']} · {alt['venue']}（总分 {alt['total']}）。")
    return "\n\n".join(lines)
