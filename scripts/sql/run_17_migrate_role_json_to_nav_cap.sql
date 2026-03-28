-- 将 role.allowed_menu_keys / allowed_capability_keys 导入关联表（inventory→双码，report_export→双码）
-- 执行前需已跑 run_15、run_16。可重复执行时用 DELETE FROM role_allowed_nav WHERE role_id IN (...) 或整表清空后重跑。

USE sydixon_order;
SET NAMES utf8mb4;

-- 清空现有关联（按需：仅迁移一次时取消注释下一行）
-- TRUNCATE TABLE role_allowed_capability;
-- TRUNCATE TABLE role_allowed_nav;

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'inventory_query' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"inventory"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'inventory_ops' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"inventory"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'report_notes' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"report_export"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'report_records' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"report_export"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, jt.`v` FROM `role` r
JOIN JSON_TABLE(r.`allowed_menu_keys`, '$[*]' COLUMNS (`v` VARCHAR(64) PATH '$')) jt
WHERE r.`allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_menu_keys`) = 'ARRAY'
  AND jt.`v` NOT IN ('inventory', 'report_export');

-- admin / pending：可不写关联（应用层 admin 全放行；pending 无菜单）
-- 若希望 admin 也在表中拥有全部叶子，可另行脚本插入

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, jt.`v` FROM `role` r
JOIN JSON_TABLE(r.`allowed_capability_keys`, '$[*]' COLUMNS (`v` VARCHAR(128) PATH '$')) jt
WHERE r.`allowed_capability_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_capability_keys`) = 'ARRAY'
  AND JSON_LENGTH(r.`allowed_capability_keys`) > 0;
