# 2026-04-10：RBAC 菜单缓存下的 admin 可见性修复

## 摘要

修复了新增菜单后 admin 可能看不到入口的问题。根因是菜单判断在 admin 分支前先校验快照内的 assignable 集合，快照滞后时会误拦截。现已调整为 admin 优先，并在快照缺失时回退 DB 校验。

## 影响范围

- 域：RBAC / Procurement（菜单展示）
- 模块：`app/auth/menus.py`

## 代码变更（要点）

- 调整 `user_can_menu` 判断顺序：先处理 `pending/admin`，再走普通角色逻辑。
- 对 admin 增加 DB 回退判定：当 `_assignable_codes()` 未命中时，查询 `sys_nav_item(code,is_active,is_assignable)` 决定是否可见。
- 避免 `procurement_material` 等新菜单在缓存未刷新窗口期对 admin 误判为不可见。

## 文档 / Skill 同步

- [x] `docs/02_domains/procurement.md`
- [x] `docs/04_ai/project-skill/rbac_and_menus.md`
- [ ] `docs/00_overview/architecture.md`（不需要）
- [ ] `docs/openclaw-skill/SKILL.md`（不需要）

## SQL / 迁移

- 新增：无
- `00_full_schema.sql`：否（本次未涉及）

## 验证

- 数据库核验：`sys_nav_item` 含 `procurement_material` 且 `is_active=1`、父级为 `nav_procurement`。
- 行为核验：admin 在缓存未即时刷新场景下，菜单仍可显示新入口。
