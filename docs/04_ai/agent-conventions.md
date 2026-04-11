# 面向 AI / 协作的约定

在修改本仓库时，除遵守 `AGENTS.md`、`.cursor/rules/*.mdc` 外，建议遵循以下约定，便于人类与 Agent 一致维护文档。

## 1. 先文档后下钻代码

1. 读 [docs/index.md](../index.md) 定位业务域。  
2. 读 [docs/02_domains/](../02_domains/) 对应域文档。  
3. 再打开 [项目 Skill 路由映射](../04_ai/project-skill/map_routes_to_services.md) 中的 `routes_*` / `*_svc.py` / `models`。  

逻辑变更后，**同步更新**域文档与 [project-skill](../04_ai/project-skill/SKILL.md) 中相关段落。

## 2. RBAC 变更

- 修改 `app/auth/menus.py`、`app/auth/capability_data.py`、`app/models/rbac.py` 或通过 `routes_role.py` / `routes_rbac_admin.py` 影响菜单与能力时：  
  - 更新 [rbac_and_menus.md](project-skill/rbac_and_menus.md) 与受影响域文档中的「权限点」小节。  
  - 若新增 `run_*` 写入 `sys_nav_item` / `sys_capability`，在域文档「相关 SQL」中记录脚本编号。

## 3. 数据库变更

- 只新增 `scripts/sql/run_NN_*.sql`，不修改已有 `run_*.sql`。  
- 同步更新 `00_full_schema.sql`（若全量 bootstrap 需反映新结构）。  
- 在域文档与 [db_rules_and_patterns.md](project-skill/db_rules_and_patterns.md) 中补充表/字段语义（如有新范式）。

## 4. OpenClaw API 变更

- 修改 `app/openclaw/routes.py` 或鉴权行为时：  
  - 评估是否更新 `docs/openclaw-skill/SKILL.md`。  
  - 在相关域文档中补充「对外 API」或链接 OpenClaw 文档。

## 5. Excel / 导入导出

- 模板在 `app/static/templates/` 或 `app/utils/*_excel.py` 时：  
  - 域文档中更新字段口径；必要时补充/更新 `tests/` 中回归用例。

## 6. 变更记录

- 非琐碎改动建议在 [docs/changes/](../changes/README.md) 按规范追加一条，便于发布与审计。
