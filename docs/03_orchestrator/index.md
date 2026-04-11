# 编排器（Orchestrator）文档索引

本目录同级已有专题文档，入口如下（路径相对本文件 `docs/03_orchestrator/`）：

| 文档 | 说明 |
|------|------|
| [orchestrator_runbook.md](../orchestrator_runbook.md) | 发布/灰度、kill switch、运维接口与命令 |
| [orchestrator_alerts.md](../orchestrator_alerts.md) | 告警来源、阈值建议、处置流程 |
| [orchestrator_event_triggers_flow.md](../orchestrator_event_triggers_flow.md) | 事件类型、payload、重放/重试（技术向） |
| [orchestrator_event_triggers_flow_biz.md](../orchestrator_event_triggers_flow_biz.md) | 业务向说明：哪些会改主数据、如何看时间线 |
| [orchestrator_uat_checklist.md](../orchestrator_uat_checklist.md) | UAT 最小清单 |
| [orchestrator_capacity.md](../orchestrator_capacity.md) | 容量与归档建议 |

## 代码入口

- 引擎：`app/services/orchestrator_engine.py`
- 契约/事件常量：`app/services/orchestrator_contracts.py`
- Web 管理路由：`app/main/routes_orchestrator.py`

## 相关

- 生产测算验收基线：[production-measurement-benchmark.md](../production-measurement-benchmark.md)
- 架构总览中的编排器小节：[architecture.md](../00_overview/architecture.md)
