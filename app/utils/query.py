"""列表模糊搜索：多列 OR LIKE。"""
from sqlalchemy import cast, String

from app import db


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
