-- 库存录入拆分为三菜单：成品 / 半成品 / 材料（独立授权）
-- 说明：不使用外键；存量库执行后建议重启应用或 invalidate_rbac_cache()

USE sydixon_order;
SET NAMES utf8mb4;

-- 1) 原 inventory_ops 仅保留为分组节点
UPDATE `sys_nav_item`
SET `endpoint` = NULL,
    `is_assignable` = 0,
    `landing_priority` = NULL
WHERE `code` = 'inventory_ops';

-- 2) 三个子菜单
INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
)
SELECT p.`id`, 'inventory_ops_finished', '成品录入', 'main.inventory_finished_entry', 10,
       1, 0, 1, 86
FROM `sys_nav_item` p WHERE p.`code` = 'inventory_ops' LIMIT 1
ON DUPLICATE KEY UPDATE
  `parent_id` = VALUES(`parent_id`),
  `title` = VALUES(`title`),
  `endpoint` = VALUES(`endpoint`),
  `sort_order` = VALUES(`sort_order`),
  `admin_only` = VALUES(`admin_only`),
  `is_assignable` = VALUES(`is_assignable`),
  `landing_priority` = VALUES(`landing_priority`);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
)
SELECT p.`id`, 'inventory_ops_semi', '半成品录入', 'main.inventory_semi_entry', 20,
       1, 0, 1, 87
FROM `sys_nav_item` p WHERE p.`code` = 'inventory_ops' LIMIT 1
ON DUPLICATE KEY UPDATE
  `parent_id` = VALUES(`parent_id`),
  `title` = VALUES(`title`),
  `endpoint` = VALUES(`endpoint`),
  `sort_order` = VALUES(`sort_order`),
  `admin_only` = VALUES(`admin_only`),
  `is_assignable` = VALUES(`is_assignable`),
  `landing_priority` = VALUES(`landing_priority`);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
)
SELECT p.`id`, 'inventory_ops_material', '材料录入', 'main.inventory_material_entry', 30,
       1, 0, 1, 88
FROM `sys_nav_item` p WHERE p.`code` = 'inventory_ops' LIMIT 1
ON DUPLICATE KEY UPDATE
  `parent_id` = VALUES(`parent_id`),
  `title` = VALUES(`title`),
  `endpoint` = VALUES(`endpoint`),
  `sort_order` = VALUES(`sort_order`),
  `admin_only` = VALUES(`admin_only`),
  `is_assignable` = VALUES(`is_assignable`),
  `landing_priority` = VALUES(`landing_priority`);

-- 3) 新能力键（三菜单各自一套）
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('inventory_ops_finished.api.products_search', '成品录入：产品搜索接口', 'inventory_ops_finished', '成品录入', 10),
('inventory_ops_finished.api.suggest_storage_area', '成品录入：仓储区建议接口', 'inventory_ops_finished', '成品录入', 20),
('inventory_ops_finished.movement.list', '成品录入：库存批次列表', 'inventory_ops_finished', '成品录入', 25),
('inventory_ops_finished.movement.create', '成品录入：手工出入库', 'inventory_ops_finished', '成品录入', 30),
('inventory_ops_finished.movement.delete', '成品录入：删除进出明细', 'inventory_ops_finished', '成品录入', 40),
('inventory_ops_finished.movement_batch.void', '成品录入：撤销手工/导入批次', 'inventory_ops_finished', '成品录入', 45),
('inventory_ops_finished.opening.list', '成品录入：期初列表', 'inventory_ops_finished', '成品录入', 50),
('inventory_ops_finished.opening.create', '成品录入：新建期初', 'inventory_ops_finished', '成品录入', 60),
('inventory_ops_finished.opening.edit', '成品录入：编辑期初', 'inventory_ops_finished', '成品录入', 70),
('inventory_ops_finished.opening.delete', '成品录入：删除期初', 'inventory_ops_finished', '成品录入', 80),
('inventory_ops_finished.daily.list', '成品录入：日结列表', 'inventory_ops_finished', '成品录入', 90),
('inventory_ops_finished.daily.create', '成品录入：新建日结', 'inventory_ops_finished', '成品录入', 100),
('inventory_ops_finished.daily.detail', '成品录入：日结详情', 'inventory_ops_finished', '成品录入', 110),
('inventory_ops_finished.daily.edit', '成品录入：编辑日结', 'inventory_ops_finished', '成品录入', 120),
('inventory_ops_finished.daily.delete', '成品录入：删除日结', 'inventory_ops_finished', '成品录入', 130),
('inventory_ops_semi.api.products_search', '半成品录入：产品搜索接口', 'inventory_ops_semi', '半成品录入', 10),
('inventory_ops_semi.api.suggest_storage_area', '半成品录入：仓储区建议接口', 'inventory_ops_semi', '半成品录入', 20),
('inventory_ops_semi.movement.list', '半成品录入：库存批次列表', 'inventory_ops_semi', '半成品录入', 25),
('inventory_ops_semi.movement.create', '半成品录入：手工出入库', 'inventory_ops_semi', '半成品录入', 30),
('inventory_ops_semi.movement.delete', '半成品录入：删除进出明细', 'inventory_ops_semi', '半成品录入', 40),
('inventory_ops_semi.movement_batch.void', '半成品录入：撤销手工/导入批次', 'inventory_ops_semi', '半成品录入', 45),
('inventory_ops_semi.opening.list', '半成品录入：期初列表', 'inventory_ops_semi', '半成品录入', 50),
('inventory_ops_semi.opening.create', '半成品录入：新建期初', 'inventory_ops_semi', '半成品录入', 60),
('inventory_ops_semi.opening.edit', '半成品录入：编辑期初', 'inventory_ops_semi', '半成品录入', 70),
('inventory_ops_semi.opening.delete', '半成品录入：删除期初', 'inventory_ops_semi', '半成品录入', 80),
('inventory_ops_semi.daily.list', '半成品录入：日结列表', 'inventory_ops_semi', '半成品录入', 90),
('inventory_ops_semi.daily.create', '半成品录入：新建日结', 'inventory_ops_semi', '半成品录入', 100),
('inventory_ops_semi.daily.detail', '半成品录入：日结详情', 'inventory_ops_semi', '半成品录入', 110),
('inventory_ops_semi.daily.edit', '半成品录入：编辑日结', 'inventory_ops_semi', '半成品录入', 120),
('inventory_ops_semi.daily.delete', '半成品录入：删除日结', 'inventory_ops_semi', '半成品录入', 130),
('inventory_ops_material.api.products_search', '材料录入：产品搜索接口', 'inventory_ops_material', '材料录入', 10),
('inventory_ops_material.api.suggest_storage_area', '材料录入：仓储区建议接口', 'inventory_ops_material', '材料录入', 20),
('inventory_ops_material.movement.list', '材料录入：库存批次列表', 'inventory_ops_material', '材料录入', 25),
('inventory_ops_material.movement.create', '材料录入：手工出入库', 'inventory_ops_material', '材料录入', 30),
('inventory_ops_material.movement.delete', '材料录入：删除进出明细', 'inventory_ops_material', '材料录入', 40),
('inventory_ops_material.movement_batch.void', '材料录入：撤销手工/导入批次', 'inventory_ops_material', '材料录入', 45),
('inventory_ops_material.opening.list', '材料录入：期初列表', 'inventory_ops_material', '材料录入', 50),
('inventory_ops_material.opening.create', '材料录入：新建期初', 'inventory_ops_material', '材料录入', 60),
('inventory_ops_material.opening.edit', '材料录入：编辑期初', 'inventory_ops_material', '材料录入', 70),
('inventory_ops_material.opening.delete', '材料录入：删除期初', 'inventory_ops_material', '材料录入', 80),
('inventory_ops_material.daily.list', '材料录入：日结列表', 'inventory_ops_material', '材料录入', 90),
('inventory_ops_material.daily.create', '材料录入：新建日结', 'inventory_ops_material', '材料录入', 100),
('inventory_ops_material.daily.detail', '材料录入：日结详情', 'inventory_ops_material', '材料录入', 110),
('inventory_ops_material.daily.edit', '材料录入：编辑日结', 'inventory_ops_material', '材料录入', 120),
('inventory_ops_material.daily.delete', '材料录入：删除日结', 'inventory_ops_material', '材料录入', 130)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

-- 4) 菜单授权：默认复制 inventory_ops 既有授权到三个子菜单
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT `role_id`, 'inventory_ops_finished' FROM `role_allowed_nav` WHERE `nav_code` = 'inventory_ops';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT `role_id`, 'inventory_ops_semi' FROM `role_allowed_nav` WHERE `nav_code` = 'inventory_ops';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT `role_id`, 'inventory_ops_material' FROM `role_allowed_nav` WHERE `nav_code` = 'inventory_ops';
DELETE FROM `role_allowed_nav` WHERE `nav_code` = 'inventory_ops';

-- 5) 能力授权：若角色已有 inventory_ops.* 能力，复制到对应三类能力并移除旧能力
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, REPLACE(rac.`cap_code`, 'inventory_ops.', 'inventory_ops_finished.')
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` LIKE 'inventory_ops.%';
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, REPLACE(rac.`cap_code`, 'inventory_ops.', 'inventory_ops_semi.')
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` LIKE 'inventory_ops.%';
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, REPLACE(rac.`cap_code`, 'inventory_ops.', 'inventory_ops_material.')
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` LIKE 'inventory_ops.%';
DELETE FROM `role_allowed_capability` WHERE `cap_code` LIKE 'inventory_ops.%';

-- 6) 兼容仍使用 role.allowed_menu_keys JSON 的场景
UPDATE `role`
SET `allowed_menu_keys` = CAST(
  REPLACE(
    CAST(`allowed_menu_keys` AS CHAR CHARSET utf8mb4),
    '"inventory_ops"',
    '"inventory_ops_finished","inventory_ops_semi","inventory_ops_material"'
  ) AS JSON
)
WHERE `allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(`allowed_menu_keys`) = 'ARRAY'
  AND JSON_CONTAINS(`allowed_menu_keys`, '"inventory_ops"', '$');
