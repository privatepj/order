# Orchestrator 运行手册

## 1. 发布前检查

- 执行增量 SQL：`run_51_orchestrator_p3_feature_flags.sql`、`run_52_orchestrator_p4_ops_flags.sql`
- 确认 `sys_feature_flag` 存在以下键：
  - `orchestrator.kill_switch`
  - `orchestrator.replay_enabled`
  - `orchestrator.retry_enabled`
  - `orchestrator.overdue_scan_enabled`
- 使用只读接口确认系统可用：
  - `GET /orchestrator/dashboard`
  - `GET /orchestrator/rules`

## 2. 灰度发布步骤

1. 将 `orchestrator.kill_switch=1`（只保留事件入库，不执行动作）。
2. 观察 10-30 分钟事件入库与审计日志是否正常。
3. 设置白名单（公司或 biz_key），仅对灰度范围放开执行。
4. 将 `orchestrator.kill_switch=0`，放量运行。
5. 观察 `failed_events/dead_actions/success_rate_24h` 指标。

## 3. 紧急回滚步骤（5 分钟内）

1. 立刻设置 `orchestrator.kill_switch=1`。
2. 如需进一步止血，设置：
   - `orchestrator.replay_enabled=0`
   - `orchestrator.retry_enabled=0`
   - `orchestrator.overdue_scan_enabled=0`
3. 通过 `GET /orchestrator/dashboard` 确认失败动作不再增长。
4. 导出当时 `orchestrator_event/orchestrator_action/orchestrator_audit_log` 证据并定位原因。

## 4. 值班排障命令

- 手动重试：`POST /orchestrator/actions/retry`
- 恢复 dead：`POST /orchestrator/actions/<id>/recover`
- 批量恢复：`POST /orchestrator/actions/recover-batch`
- 条件重放：`POST /orchestrator/events/<id>/replay-advanced`
- 扫描超时单：`POST /orchestrator/scan/overdue`

## 5. 常见场景

- replay 被关闭：返回 `replay 已被运行开关关闭。`
- retry 被关闭：重试接口返回 `retried=0`
- overdue scan 被关闭：返回 `overdue scan 已被运行开关关闭。`
