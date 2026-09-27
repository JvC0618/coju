"""Grounded presentation text; optional LLM parsing remains an unconnected extension."""
import json
import config


def parse_request(text, fallback_members=None):
    """Reserved extension. Current UI uses explicit form inputs, not this parser."""
    if not config.LLM_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL, timeout=20)
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[{"role": "system", "content": "只提取用户提供的聚会参数为JSON，不添加事实。字段members、budget、prefs、time。"},
                      {"role": "user", "content": text}],
            response_format={"type": "json_object"}, temperature=0)
        return json.loads(response.choices[0].message.content)
    except Exception:
        return None


def generate_plan(top_candidates, members, budget, prefs):
    """Use the scored facts only; never assert a city-wide fairness optimum."""
    if not top_candidates:
        return "本次没有找到满足条件且通勤数据完整的候选，请调整条件后重试。"
    best = top_candidates[0]
    lines = [f"建议在 **{best['venue']}** 集合（{best['neighborhood']}）。",
             f"按当前权重，它在本次有效候选中综合得分最高：**{best['total']:.3f}**。",
             f"{len(members)}位成员的平均通勤时间为 **{best['avg_commute_min']} 分钟**，"
             f"最长与最短相差 **{best['commute_gap_min']} 分钟**。"]
    if best["commute_gap_min"] >= 30:
        lines.append("通勤差距仍较大，可以比较其他候选或调整出发地点。")
    cost = best.get("cost")
    lines.append(f"人均参考消费：{f'{cost:g}元' if cost is not None and cost > 0 else '暂无数据'}；你的预算为{budget:g}元/人。")
    if cost is not None and cost > budget:
        lines.append("这家餐厅的人均参考消费高于预算，请注意比较。")
    rating = best.get("rating")
    lines.append(f"餐厅原始评分：{f'{rating:g}/5' if rating is not None and rating > 0 else '暂无数据'}；"
                 f"营业时间：{best.get('hours') or '暂无数据，请向商家确认'}。")
    if len(top_candidates) > 1:
        alt = top_candidates[1]
        lines.append(f"备选：**{alt['venue']}**（综合得分 {alt['total']:.3f}）。")
    return "\n\n".join(lines)

