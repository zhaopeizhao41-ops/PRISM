"""Lightweight safety-topic detection for user-facing decision warnings."""

from typing import Any, Dict, Iterable, List


_TOPIC_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "finance": (
        "财务", "现金", "债务", "贷款", "投资", "股票", "理财", "税", "收入", "薪资", "预算",
        "finance", "money", "cash", "debt", "loan", "invest", "stock", "tax", "income", "budget",
    ),
    "health": (
        "健康", "医疗", "医生", "症状", "疾病", "药", "治疗", "诊断", "心理", "抑郁", "焦虑",
        "health", "medical", "doctor", "symptom", "disease", "medication", "treatment", "diagnosis", "therapy",
    ),
    "legal": (
        "法律", "合同", "诉讼", "律师", "违法", "版权", "租约", "离婚", "法院",
        "legal", "contract", "lawsuit", "lawyer", "court", "copyright", "lease", "divorce",
    ),
}


def _text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _text_values(child)
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _text_values(child)


def detect_risk_topics(value: Any) -> List[str]:
    """Return stable topic codes found in a decision context.

    This is intentionally conservative and only drives a safety reminder. It
    does not classify the user, alter prompts, or block any workflow.
    """
    text = " ".join(_text_values(value)).casefold()
    return [
        topic
        for topic, keywords in _TOPIC_KEYWORDS.items()
        if any(keyword.casefold() in text for keyword in keywords)
    ]
