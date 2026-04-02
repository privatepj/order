# Orchestrator 容量治理建议

## 1. 批处理上限

- `retry_due_actions` 单次最多 500 条。
- `get_order_timeline` 单次最多 1000 条候选事件。
- `recover_dead_actions_batch` 单次最多 500 条。

## 2. 索引策略

- 运行 `run_53_orchestrator_p4_perf_indexes.sql` 后，重点受益查询：
  - 失败/死信统计
  - 24h 看板统计
  - replay blocked 统计

## 3. 数据增长与保留

- `orchestrator_event/action/audit` 建议按月归档。
- `orchestrator_audit_log` 建议保留 90 天热数据。
- `orchestrator_replay_job` 建议保留 180 天追溯数据。

## 4. 压测建议

- 每次发布前执行：
  - ingest 500~2000 条事件压测
  - run/retry/replay-advanced 并发压测
- 重点监控：平均延迟、错误率、数据库连接池占用。
