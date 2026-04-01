"""列表模糊搜索：多列 OR LIKE。"""
from __future__ import annotations

from sqlalchemy import cast, String

from app import db

# 客户类搜索（列表 / OpenClaw / JSON 搜索）须带关键字，避免空条件枚举。
# 允许单字符关键字，避免短码/简称无法命中。
MIN_CUSTOMER_SEARCH_KEYWORD_LEN = 1


def is_valid_customer_search_keyword(keyword: str | None) -> bool:
    """关键字非空且长度达到下限，才允许执行客户查询。"""
    s = (keyword or "").strip()
    return len(s) >= MIN_CUSTOMER_SEARCH_KEYWORD_LEN


def keyword_like_or(keyword, *columns):
    """
    keyword 非空时返回 or_(col.like(%kw%)...)。
    tax_point 等数值列可先 cast(String) 再传入。
    """
    if not (keyword or "").strip():
        return None
    like = f"%{keyword.strip()}%"
    return db.or_(*[c.like(like) for c in columns])


def cast_str(col):
    return cast(col, String)
