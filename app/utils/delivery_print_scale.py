"""送货单浏览器打印字号比例（进程内存，不落库；进程重启恢复为 1.0）。"""

import threading
from typing import Tuple

_MIN = 0.5
_MAX = 2.0

_lock = threading.Lock()
_scale: float = 1.0


def get_delivery_print_font_scale() -> float:
    with _lock:
        return _scale


def set_delivery_print_font_scale(value: float) -> Tuple[bool, str]:
    """返回 (ok, message)。message 在 ok 为 False 时为错误说明。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False, "比例须为数字。"
    if v < _MIN or v > _MAX:
        return False, f"比例须在 {_MIN}～{_MAX} 之间。"
    global _scale
    with _lock:
        _scale = v
    return True, ""
