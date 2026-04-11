-- 回填混合态 RBAC 的菜单授权：对仍保留 allowed_menu_keys JSON 的历史角色，
-- 将缺失的 role_allowed_nav 补齐，避免部分迁移后新表记录覆盖旧菜单语义。
-- 可重复执行；仅追加缺失数据，不删除任何现有授权。

USE sydixon_order;
SET NAMES utf8mb4;

-- 1) 直接回填 allowed_menu_keys 中仍与当前可分配菜单编码同名的授权
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, n.`code`
FROM `role` r
JOIN `sys_nav_item` n
  ON n.`is_active` = 1
 AND n.`is_assignable` = 1
WHERE r.`allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_menu_keys`) = 'ARRAY'
  AND JSON_CONTAINS(r.`allowed_menu_keys`, JSON_QUOTE(n.`code`), '$');

-- 2) 兼容旧 inventory 菜单枚举：展开为库存查询 + 三类库存录入
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, expanded.`nav_code`
FROM `role` r
JOIN (
  SELECT 'inventory_query' AS `nav_code`
  UNION ALL SELECT 'inventory_ops_finished'
  UNION ALL SELECT 'inventory_ops_semi'
  UNION ALL SELECT 'inventory_ops_material'
) expanded
WHERE r.`allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_menu_keys`) = 'ARRAY'
  AND JSON_CONTAINS(r.`allowed_menu_keys`, '"inventory"', '$');

-- 3) 兼容旧 inventory_ops 菜单枚举：展开为三类库存录入
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, expanded.`nav_code`
FROM `role` r
JOIN (
  SELECT 'inventory_ops_finished' AS `nav_code`
  UNION ALL SELECT 'inventory_ops_semi'
  UNION ALL SELECT 'inventory_ops_material'
) expanded
WHERE r.`allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_menu_keys`) = 'ARRAY'
  AND JSON_CONTAINS(r.`allowed_menu_keys`, '"inventory_ops"', '$');

-- 4) 兼容旧 production 枚举：展开为当前已拆分的两个主功能
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, expanded.`nav_code`
FROM `role` r
JOIN (
  SELECT 'production_preplan' AS `nav_code`
  UNION ALL SELECT 'production_incident'
) expanded
WHERE r.`allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_menu_keys`) = 'ARRAY'
  AND JSON_CONTAINS(r.`allowed_menu_keys`, '"production"', '$');

-- 5) 兼容旧报表分组枚举
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, expanded.`nav_code`
FROM `role` r
JOIN (
  SELECT 'report_notes' AS `nav_code`
  UNION ALL SELECT 'report_records'
) expanded
WHERE r.`allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_menu_keys`) = 'ARRAY'
  AND JSON_CONTAINS(r.`allowed_menu_keys`, '"report_export"', '$');
