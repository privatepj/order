from __future__ import annotations

from typing import Dict, Set, Tuple


ORDER_STAGES = (
    "draft",
    "confirmed",
    "waiting_material",
    "ready_production",
    "in_production",
    "waiting_qc",
    "ready_delivery",
    "done",
    "closed",
)

ORDER_STAGE_TRANSITIONS: Dict[str, Set[str]] = {
    "draft": {"confirmed", "closed"},
    "confirmed": {"waiting_material", "ready_production", "closed"},
    "waiting_material": {"ready_production", "closed"},
    "ready_production": {"in_production", "closed"},
    "in_production": {"waiting_qc", "closed"},
    "waiting_qc": {"ready_delivery", "closed"},
    "ready_delivery": {"done", "closed"},
    "done": set(),
    "closed": set(),
}


def is_valid_transition(current_stage: str, next_stage: str) -> bool:
    if current_stage not in ORDER_STAGE_TRANSITIONS:
        return False
    return next_stage in ORDER_STAGE_TRANSITIONS[current_stage]


def validate_hard_constraints(
    *,
    target_stage: str,
    material_ready: bool,
    qc_passed: bool,
    has_delivery_items: bool,
) -> Tuple[bool, str]:
    if target_stage == "in_production" and not material_ready:
        return False, "未齐套，不可进入生产中。"
    if target_stage in ("ready_delivery", "done") and not qc_passed:
        return False, "未质检通过，不可进入发货阶段。"
    if target_stage == "done" and not has_delivery_items:
        return False, "无发货记录，不可置为完成。"
    return True, ""
