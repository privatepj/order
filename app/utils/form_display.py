"""可选文本字段：避免字面量 'None' 回显与再次落库。"""

from __future__ import annotations

from typing import Any, Optional


def clean_optional_text(raw: Any, *, max_len: Optional[int] = None) -> Optional[str]:
    """
    保存前规范化：空白、仅空白、不区分大小写的字面量 \"none\" → None。
    非字符串会先 str() 再 strip（兼容 Excel 等来源）。
    """
    if raw is None:
        return None
    s = raw.strip() if isinstance(raw, str) else str(raw).strip()
    if max_len is not None and len(s) > max_len:
        s = s[:max_len]
    if not s or s.lower() == "none":
        return None
    return s


def form_blank(value: Any) -> str:
    """
    Jinja 过滤器：ORM 为 None 或误存字面量 'None' 时，表单控件展示为空串。
    """
    if value is None:
        return ""
    if isinstance(value, str) and value.strip().lower() == "none":
        return ""
    if isinstance(value, str):
        return value
    return str(value)
