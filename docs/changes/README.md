# 变更记录与文档同步规范

## 目的

保证 **代码与 `docs/`、`docs/04_ai/project-skill/`** 一致：逻辑、权限、库表或对外 API 变了，文档与 Skill 能跟进，避免「只改实现不更新知识库」。

## 何时必须更新文档

| 改动类型 | 至少更新 |
|----------|----------|
| 业务流程、状态机、计算口径 | `docs/02_domains/<域>.md`；必要时 [project-skill 域速查](../04_ai/project-skill/domain_quickrefs/index.md) |
| 菜单/能力/导航 | `docs/04_ai/project-skill/rbac_and_menus.md` + 受影响域文档「权限」小节 + [map_routes_to_services.md](../04_ai/project-skill/map_routes_to_services.md) |
| 表结构、`run_NN`、ORM 关系 | `docs/01_development/db-migrations.md` 或域文档「相关 SQL」；[db_rules_and_patterns.md](../04_ai/project-skill/db_rules_and_patterns.md) |
| OpenClaw 入参/出参/鉴权 | `docs/openclaw-skill/SKILL.md`（若适用）+ 相关域文档 |
| Orchestrator 事件/动作语义 | `docs/orchestrator_*.md` 或 [03_orchestrator/index.md](../03_orchestrator/index.md) 所指专题文 |
| 跨域架构边界变化 | `docs/00_overview/architecture.md` |

## 本目录怎么用

- 每条记录一个**主题**（可按日期或 PR 分支命名文件）。  
- 推荐文件名：`YYYY-MM-DD_short-topic.md`（短英文或拼音 slug 均可）。  
- 模板见 [_TEMPLATE.md](_TEMPLATE.md)。

## 可选检查

本地可运行（提醒性质，默认不因未改 docs 而失败）：

```bash
python scripts/check_docs_sync.py
```

严格模式（例如在 CI 中）：

```bash
python scripts/check_docs_sync.py --strict
```

详见脚本内说明。
