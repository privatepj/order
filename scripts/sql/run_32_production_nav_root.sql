-- 生产管理：从「仓管」子菜单提升为顶级菜单（与 00_full_schema / run_31 修正后一致）
-- 无外键约束
-- 部署后请重启应用或调用 invalidate_rbac_cache()，以便导航缓存加载新 parent_id。

USE sydixon_order;
SET NAMES utf8mb4;

UPDATE `sys_nav_item`
SET `parent_id` = NULL, `sort_order` = 15
WHERE `code` = 'production';
