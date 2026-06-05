"""
AI 文本生成 — 调用 Claude API 基于评分数据生成风险描述和建议动作。

设计决策 D2：LLM 仅用于文本生成，不参与评分计算。
使用 claude-sonnet-4-6（Q2 决定：报告是正式决策文件，质量优先）。
AI 调用失败时降级返回占位文本，不阻断报告生成。
"""
from __future__ import annotations
import hashlib
import json
from typing import Optional
from src.scoring import ScoringResult

FALLBACK_RISKS = ["[AI 分析不可用 - 请采购经理手动填写]"]
FALLBACK_ACTIONS = ["[AI 建议不可用 - 请采购经理手动填写]"]

_RISK_SYSTEM_PROMPT = """你是卓品智能科技采购部的风险分析助手。
你的任务：基于供应商评分数据，用中文写出核心风险描述。

严格规则：
1. 只能基于提供的评分数字和维度说明进行分析，禁止推测未提供的信息
2. 每条描述不超过50字
3. 优先描述评分最低的维度
4. 输出格式：JSON 数组，最多3个字符串元素
5. 只输出 JSON，不要任何解释文字"""

_ACTION_SYSTEM_PROMPT = """你是卓品智能科技采购部的采购决策顾问。
你的任务：基于供应商风险评估结果，给出具体可执行的建议动作。

规则：
1. 风险等级4-5级时必须包含"考虑启动替代供应商开发"
2. 交付维度评分≤2时包含"启动供应商绩效改善计划（SIP）"
3. IQC维度评分≤2时包含"要求供应商提交质量整改报告（8D）"
4. 风险等级1-2级时以"维持现状"或"加入优选供应商清单"为主
5. 每条建议不超过50字，最多3条
6. 只能基于提供的数据，禁止推断
7. 输出格式：JSON 数组，最多3个字符串元素
8. 只输出 JSON，不要任何解释文字"""


def _build_scoring_context(result: ScoringResult, supplier_name: str) -> str:
    return json.dumps({
        "supplier": supplier_name,
        "composite_score": result.composite_score,
        "risk_level": result.risk_level,
        "risk_label": result.risk_label,
        "scores": {
            "delivery": result.delivery.value,
            "iqc": result.iqc.value,
            "financial": result.financial.value,
            "single_source": result.single_source.value,
        },
        "data_sources": {
            "delivery": result.delivery.source or "正常",
            "iqc": result.iqc.source or "正常",
            "financial": result.financial.source or "正常",
            "single_source": result.single_source.source or "正常",
        },
    }, ensure_ascii=False, indent=2)


def _call_claude(system_prompt: str, user_content: str, api_key: str, model: str) -> list[str]:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = message.content[0].text.strip()
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return [str(item) for item in parsed[:3]]
    return [str(parsed)]


def generate_ai_text(
    result: ScoringResult,
    supplier_name: str,
    api_key: str,
    model: str = "claude-sonnet-4-6",
) -> tuple[list[str], list[str], str]:
    """
    生成核心风险描述和建议动作。

    Returns:
        (risk_descriptions, action_items, ai_text_hash)
        失败时返回 (FALLBACK_RISKS, FALLBACK_ACTIONS, "")
    """
    context = _build_scoring_context(result, supplier_name)

    try:
        risks = _call_claude(_RISK_SYSTEM_PROMPT, context, api_key, model)
    except Exception:
        risks = FALLBACK_RISKS

    try:
        actions = _call_claude(_ACTION_SYSTEM_PROMPT, context, api_key, model)
    except Exception:
        actions = FALLBACK_ACTIONS

    combined = json.dumps({"risks": risks, "actions": actions}, ensure_ascii=False)
    ai_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    return risks, actions, ai_hash
