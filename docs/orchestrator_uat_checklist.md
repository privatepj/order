# Orchestrator UAT 清单

## 1. 缺料触发链路

- 输入：创建 `order.changed`（缺料场景）
- 预期：生成 `CreatePreplan` + `CreateProcurementRequest`
- 证据：
  - `orchestrator_event.status`
  - `orchestrator_action.action_type`
  - `orchestrator_audit_log.message=rule_profile_hit`
  - `/orchestrator/orders/<id>/timeline`
- 回滚点：`orchestrator.kill_switch=1`

## 2. 报工推进链路

- 输入：`production.operation_reported`
- 预期：产生 `MoveOrderStatus`
- 证据：event/action/audit/timeline 四类一致
- 回滚点：关闭执行开关并重放修正

## 3. 质检失败分支

- 输入：`quality.failed`
- 预期：`TriggerQualityHold` + `TriggerQualityRework`
- 证据：action 列表包含双动作；审计有失败/执行记录
- 回滚点：恢复 dead + 条件重放

## 4. 逾期扫描链路

- 输入：手动触发 `/orchestrator/scan/overdue`
- 预期：按逾期订单产生采购建议动作
- 证据：`EVENT_ORDER_OVERDUE_SCAN` 对应动作计数与明细
- 回滚点：`orchestrator.overdue_scan_enabled=0`

## 5. 重放修复链路

- 输入：`/orchestrator/events/<id>/replay-advanced`
- 预期：支持 dry-run / selected_actions / 风险阻断
- 证据：`orchestrator_replay_job` 的 `status/blocked_actions/selected_actions`
- 回滚点：`orchestrator.replay_enabled=0`
