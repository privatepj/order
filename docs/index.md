# 项目文档总入口

本目录为 **sydixon-order** 的长期有效文档；发布批次快照见 [05_releases/](05_releases/index.md)。

## 快速导航

| 分类 | 说明 |
|------|------|
| [00_overview/architecture.md](00_overview/architecture.md) | 架构一页式总览（分层、横切能力、跨域协作） |
| [01_development/dev-setup.md](01_development/dev-setup.md) | 本地开发、测试、代码风格 |
| [01_development/db-migrations.md](01_development/db-migrations.md) | 数据库：全量 schema、增量 `run_XX`、无外键与 ORM 约定 |
| [02_domains/](02_domains/) | 按业务域的稳定说明（概念、流程、路由/服务/模型入口） |
| [03_orchestrator/index.md](03_orchestrator/index.md) | 编排器文档索引 |
| [04_ai/agent-conventions.md](04_ai/agent-conventions.md) | 面向 AI/协作的跨域约定 |
| [04_ai/project-skill/SKILL.md](04_ai/project-skill/SKILL.md) | **项目 Skill**（改代码前先读；逻辑变更须同步更新） |
| [04_ai/openclaw-skill/](openclaw-skill/README.md) | OpenClaw 对外 API 的 Skill（与项目 Skill 互补） |
| [05_releases/index.md](05_releases/index.md) | 增量部署/发布快照归档 |
| [changes/README.md](changes/README.md) | 变更记录与「文档同步」规范 |

## 业务域文档（02_domains）

- [order.md](02_domains/order.md) — 订单
- [delivery.md](02_domains/delivery.md) — 送货
- [inventory.md](02_domains/inventory.md) — 库存台账
- [procurement.md](02_domains/procurement.md) — 采购（占位/待扩充）
- [production.md](02_domains/production.md) — 生产（占位/待扩充）
- [hr.md](02_domains/hr.md) — 人力（占位/待扩充）
- [machine.md](02_domains/machine.md) — 机台（占位/待扩充）
- [bom.md](02_domains/bom.md) — BOM（占位/待扩充）
- [semi-material.md](02_domains/semi-material.md) — 半成品/物料主数据（占位/待扩充）

## 仓库根目录说明类文档

- [../README.md](../README.md) — 项目简介与快速启动
- [../AGENTS.md](../AGENTS.md) — 贡献者与 Agent 规范
- [../CLAUDE.md](../CLAUDE.md) — AI 助手速查卡
- [../项目整体部署.md](../项目整体部署.md) — 部署与运维
- [../RELEASES.md](../RELEASES.md) — 指向发布快照索引
