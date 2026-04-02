# Orchestrator 告警阈值

## 健康检查来源

- API：`GET /orchestrator/health`
- CLI：`flask orchestrator-health-check`

## 建议阈值

- `dead_actions > 0`：立即告警（P1）
- `failed_events_24h > 10`：高优先级告警（P1）
- `success_rate_24h < 0.90`：高优先级告警（P1）
- `replay_blocked_24h` 突增：中优先级告警（P2）
- `scan_actions_24h` 异常为 0：中优先级告警（P2）

## 处理流程

1. 先查健康接口与 dashboard。
2. 查 `orchestrator_audit_log` 最近异常消息。
3. 必要时打开 kill switch 止血。
4. 对失败动作执行 recover/retry/replay-advanced。
5. 记录根因与处理结论，更新 runbook。
