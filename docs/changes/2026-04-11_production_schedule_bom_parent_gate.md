# 预计划排程：BOM 子工单完工后再排父工单

## 行为

- `production_schedule_svc.plan_operations_for_preplan`：对 `production_component_need` 中 `shortage_qty>0` 且 `child_kind` 为 `finished`/`semi` 的行，在同预计划、同 `root_preplan_line_id` 下匹配子工单，父工单开工门控为 `max(plan_date 零点, 子工单末 EF)`；多子件取子末 EF 的最大值。
- `production_preplan_schedule_manual_svc.validate_preplan_schedule`：追加 `list_bom_work_order_gate_errors`，要求父工单各工序 ES 的最小值不得早于依赖子工单各工序 EF 的最大值。

## 代码

- `app/services/production_schedule_svc.py`
- `app/services/production_preplan_schedule_manual_svc.py`
- `tests/test_production_schedule_bom_gate.py`

## 数据库

无 schema 变更。
