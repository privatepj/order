"""HR 敏感信息展示：脱敏与权限配合 current_user_can_cap('hr_employee.view_sensitive')。"""

from __future__ import annotations


def mask_phone(phone: str | None) -> str:
    if not phone or len(phone) < 7:
        return phone or ""
    return phone[:3] + "****" + phone[-4:]


def mask_id_card(id_card: str | None) -> str:
    if not id_card or len(id_card) < 8:
        return "****" if id_card else ""
    return id_card[:4] + "********" + id_card[-4:]


def display_phone(phone: str | None, *, sensitive: bool) -> str:
    if not phone:
        return ""
    return phone if sensitive else mask_phone(phone)


def display_id_card(id_card: str | None, *, sensitive: bool) -> str:
    if not id_card:
        return ""
    return id_card if sensitive else mask_id_card(id_card)
