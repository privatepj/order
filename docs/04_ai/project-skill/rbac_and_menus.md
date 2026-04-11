# RBAC 与菜单（速查）

## 模型与数据

- `app/models/rbac.py`：`sys_nav_item`、`sys_capability`、`role_allowed_nav`、`role_allowed_capability`
- `app/models/user.py`：`Role` 上 **resolved** 菜单/能力（含历史 JSON 字段与新表 **并集** 的混合模式）

## 运行时行为

- **菜单**：`app/auth/menus.py` — `user_can_menu`、`nav_tree_for_user`、`first_landing_url`；库表无数据时有静态兜底 `_fallback_nav_specs()`。
- **能力**：`app/auth/capabilities.py` — `user_can_cap`；`admin` 全放行，`pending` 全拒绝；普通角色需能力在注册集中且**对应菜单已授权**。
- **装饰器**：`app/auth/decorators.py` — `menu_required(...)`（页面）、`capability_required(...)`（操作，OR 语义）。
- **缓存**：`app/auth/rbac_cache.py` — 导航与能力元数据进程内快照；**保存角色或改 sys_nav/sys_capability 后必须 `invalidate_rbac_cache()`**（见 `routes_role.py`、`routes_rbac_admin.py`）。

## 常见坑：新增菜单后 admin 看不到

- 现象：库里已有 `sys_nav_item`（如 `procurement_material`）且 `is_active=1`，但顶栏不显示。
- 原因：菜单树渲染依赖 `current_user_can_menu`；若进程内 RBAC 快照滞后，新菜单可能不在 `_assignable_codes()` 中。
- 现实现约束：`admin` 分支优先于快照门禁判断。即便快照暂未刷新，也会回退到 `sys_nav_item` 读取 `is_active=1 and is_assignable=1` 进行判定，避免 admin 被误拦截。
- 排查顺序：
  1. 查 `sys_nav_item` 是否存在目标 code、`is_active=1`、父级正确；
  2. 确认路由 endpoint 与 `sys_nav_item.endpoint` 一致；
  3. 若为多进程部署，确保各实例已重载；
  4. 若通过管理页改授权，确认已触发 `invalidate_rbac_cache()`。

## 修改 RBAC 时的文档同步

- 更新 `app/auth/capability_data.py` / `menus.py` 或 SQL 种子：同步 **域文档**「权限」小节与本文件说明。  
- 新增菜单 endpoint：确认 `sys_nav_item.endpoint` 与蓝图路由一致。

## 相关文件

- 模板全局：`app/__init__.py` 中 `context_processor` 注入 `nav_tree`、`user_can_cap` 等。
- 当前导航约定：`machine_schedule`（机台排班）与 `hr_employee_schedule`（人员排产）归属 `production`（生产管理）菜单组。
