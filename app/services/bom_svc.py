from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import joinedload

from app.models import BomHeader, SemiMaterial


PARENT_FINISHED = "finished"
PARENT_SEMI = "semi"
PARENT_MATERIAL = "material"

LEAF_KINDS = (PARENT_SEMI, PARENT_MATERIAL)
CHILD_KINDS = (PARENT_SEMI, PARENT_MATERIAL)


def _parse_qty(q) -> Decimal:
    if q is None:
        return Decimal(0)
    if isinstance(q, Decimal):
        return q
    return Decimal(str(q))


def _parent_key(parent_kind: str, parent_id: int) -> Tuple[str, int]:
    if parent_kind == PARENT_FINISHED:
        return (PARENT_FINISHED, int(parent_id))
    if parent_kind in (PARENT_SEMI, PARENT_MATERIAL):
        return (parent_kind, int(parent_id))
    raise ValueError("parent_kind 只能是 finished/semi/material。")


def get_active_bom_header(parent_kind: str, parent_id: int) -> Optional[BomHeader]:
    """取“当前生效”的 BOM header（不含递归展开）。"""
    key = _parent_key(parent_kind, parent_id)
    q = BomHeader.query.filter(BomHeader.is_active.is_(True), BomHeader.parent_kind == key[0])
    if key[0] == PARENT_FINISHED:
        q = q.filter(BomHeader.parent_product_id == key[1], BomHeader.parent_material_id == 0)
    else:
        q = q.filter(BomHeader.parent_material_id == key[1], BomHeader.parent_product_id == 0)
    return q.options(joinedload(BomHeader.lines)).first()


def validate_bom_lines(
    *,
    parent_kind: str,
    parent_id: int,
    lines: List[Dict[str, Any]],
    max_depth: int = 20,
) -> None:
    """校验 BOM 明细：存在性、数量、循环引用检测（基于“保存后”的 root 边）。"""

    root_kind, root_id = _parent_key(parent_kind, parent_id)

    # 基本结构校验
    if not isinstance(lines, list):
        raise ValueError("lines 格式错误。")

    parsed: List[Dict[str, Any]] = []
    for idx, line_item in enumerate(lines, start=1):
        if not isinstance(line_item, dict):
            raise ValueError("lines 元素格式错误。")
        child_kind = (line_item.get("child_kind") or "").strip()
        child_material_id = line_item.get("child_material_id") or 0
        quantity = line_item.get("quantity") or 0
        line_no = line_item.get("line_no") or idx

        if child_kind not in CHILD_KINDS:
            raise ValueError("子项类别只能是 semi/material。")
        try:
            child_material_id = int(child_material_id)
        except Exception:
            child_material_id = 0
        if not child_material_id:
            raise ValueError("子项半成品/物料不能为空。")

        try:
            line_no = int(line_no)
        except Exception:
            line_no = idx
        if line_no <= 0:
            raise ValueError("行号必须大于 0。")

        qty = _parse_qty(quantity)
        if qty <= 0:
            raise ValueError("用量数量必须大于 0。")

        sm = SemiMaterial.query.get(child_material_id)
        if not sm or sm.kind != child_kind:
            raise ValueError("存在无效的子项半成品/物料。")

        parsed.append(
            {
                "line_no": line_no,
                "child_kind": child_kind,
                "child_material_id": child_material_id,
                "quantity": qty,
            }
        )

    # 循环引用检测：根节点用“保存后的 root 边”，其他节点使用 DB 当前生效 BOM。
    root_node = (root_kind, root_id)
    visiting: Set[Tuple[str, int]] = set()
    visiting_stack: List[Tuple[str, int]] = []

    def dfs(node_kind: str, node_id: int, depth: int) -> None:
        if depth > max_depth:
            raise ValueError("BOM 展开层级超过上限，请检查是否存在异常层级或循环引用。")

        nk, ni = _parent_key(node_kind, node_id)
        node = (nk, ni)
        if node in visiting:
            # visiting_stack 中必然包含 node 的某段路径
            cycle_idx = 0
            for i, t in enumerate(visiting_stack):
                if t == node:
                    cycle_idx = i
                    break
            cycle_seq = visiting_stack[cycle_idx:] + [node]
            return_seq = " -> ".join([f"{k}:{i}" for k, i in cycle_seq])
            raise ValueError(f"检测到 BOM 循环引用：{return_seq}")

        visiting.add(node)
        visiting_stack.append(node)

        if node == root_node:
            node_lines = parsed
        else:
            header = get_active_bom_header(parent_kind=nk, parent_id=ni)
            if header and header.lines:
                node_lines = sorted(header.lines, key=lambda x: x.line_no)
                node_lines = [
                    {
                        "child_kind": x.child_kind,
                        "child_material_id": x.child_material_id,
                    }
                    for x in node_lines
                ]
            else:
                node_lines = []

        if node_lines:
            for ln in node_lines:
                dfs(
                    ln.get("child_kind"),
                    ln.get("child_material_id"),
                    depth + 1,
                )

        visiting_stack.pop()
        visiting.remove(node)

    # 如果 root 没有边，直接返回
    if parsed:
        dfs(root_kind, root_id, depth=0)


def expand_bom_to_leaves(
    *,
    parent_kind: str,
    parent_id: int,
    quantity: Decimal | int | float = 1,
    max_depth: int = 20,
) -> List[Dict[str, Any]]:
    """递归展开 BOM，并将“无继续生效 BOM 的子项”聚合为叶子清单。"""
    root_kind, root_id = _parent_key(parent_kind, parent_id)
    qty_root = _parse_qty(quantity)
    if qty_root <= 0:
        return []

    header_cache: Dict[Tuple[str, int], Optional[BomHeader]] = {}
    leaf_qty: DefaultDict[int, Decimal] = defaultdict(lambda: Decimal(0))
    visiting: Set[Tuple[str, int]] = set()
    visiting_stack: List[Tuple[str, int]] = []

    def load_header(kind: str, pid: int) -> Optional[BomHeader]:
        key = _parent_key(kind, pid)
        if key in header_cache:
            return header_cache[key]
        h = get_active_bom_header(kind, pid)
        header_cache[key] = h
        return h

    def dfs(kind: str, pid: int, mul: Decimal, depth: int) -> None:
        nonlocal leaf_qty
        if depth > max_depth:
            raise ValueError("BOM 展开层级超过上限，请检查是否存在异常层级或循环引用。")

        nk, ni = _parent_key(kind, pid)
        node = (nk, ni)
        if node in visiting:
            cycle_seq = visiting_stack[visiting_stack.index(node) :] + [node]
            cycle_seq_s = " -> ".join([f"{k}:{i}" for k, i in cycle_seq])
            raise ValueError(f"检测到 BOM 循环引用：{cycle_seq_s}")

        header = load_header(nk, ni)
        node_lines = []
        if header and header.lines:
            node_lines = sorted(header.lines, key=lambda x: x.line_no)

        # 叶子判断：无生效 BOM 时，若为 semi/material 则计入；若起点为 finished 则不计入。
        if not node_lines:
            if nk in LEAF_KINDS:
                leaf_qty[ni] += mul
            return

        visiting.add(node)
        visiting_stack.append(node)

        for ln in node_lines:
            child_kind = ln.child_kind
            child_id = ln.child_material_id
            dfs(child_kind, child_id, mul * _parse_qty(ln.quantity), depth + 1)

        visiting_stack.pop()
        visiting.remove(node)

    # finished 起点无 BOM 时返回空；其他起点无 BOM 时当成叶子
    dfs(root_kind, root_id, qty_root, depth=0)

    if not leaf_qty:
        return []

    mids = list(leaf_qty.keys())
    sm_rows = SemiMaterial.query.filter(SemiMaterial.id.in_(mids)).all()
    sm_map = {s.id: s for s in sm_rows}

    out: List[Dict[str, Any]] = []
    for mid, q in sorted(leaf_qty.items(), key=lambda x: x[0]):
        sm = sm_map.get(mid)
        out.append(
            {
                "kind": sm.kind if sm else None,
                "material_id": mid,
                "quantity": q,
                "unit": (sm.base_unit if sm else None),
                "code": (sm.code if sm else None),
                "name": (sm.name if sm else None),
                "spec": (sm.spec if sm else None),
            }
        )
    return out


def validate_bom_import_batch(
    *,
    groups: Dict[Tuple[str, int], List[Dict[str, Any]]],
    max_depth: int = 20,
) -> None:
    """校验整批导入 groups（含“本批覆盖 + 现网沿用”）是否会形成循环引用。"""
    if not groups:
        return

    for (pk, pid), lines in groups.items():
        validate_bom_lines(parent_kind=pk, parent_id=pid, lines=lines, max_depth=max_depth)

    header_cache: Dict[Tuple[str, int], Optional[BomHeader]] = {}
    visiting: Set[Tuple[str, int]] = set()
    visiting_stack: List[Tuple[str, int]] = []

    def _db_lines(kind: str, pid: int) -> List[Dict[str, Any]]:
        key = _parent_key(kind, pid)
        if key in header_cache:
            header = header_cache[key]
        else:
            header = get_active_bom_header(parent_kind=key[0], parent_id=key[1])
            header_cache[key] = header
        if not header or not header.lines:
            return []
        return [
            {
                "child_kind": ln.child_kind,
                "child_material_id": ln.child_material_id,
            }
            for ln in sorted(list(header.lines), key=lambda x: x.line_no)
        ]

    def dfs(node_kind: str, node_id: int, depth: int) -> None:
        if depth > max_depth:
            raise ValueError("BOM 展开层级超过上限，请检查是否存在异常层级或循环引用。")
        nk, ni = _parent_key(node_kind, node_id)
        node = (nk, ni)
        if node in visiting:
            cycle_seq = visiting_stack[visiting_stack.index(node) :] + [node]
            cycle_seq_s = " -> ".join([f"{k}:{i}" for k, i in cycle_seq])
            raise ValueError(f"检测到 BOM 循环引用：{cycle_seq_s}")

        visiting.add(node)
        visiting_stack.append(node)
        if node in groups:
            lines = groups[node]
        else:
            lines = _db_lines(nk, ni)
        for ln in lines:
            dfs(ln.get("child_kind"), ln.get("child_material_id"), depth + 1)
        visiting_stack.pop()
        visiting.remove(node)

    for pk, pid in groups.keys():
        dfs(pk, pid, depth=0)

