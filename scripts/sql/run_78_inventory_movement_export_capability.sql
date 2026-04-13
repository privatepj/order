-- 库存进出明细导出能力：三类库存录入菜单新增 movement.export
USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('inventory_ops_finished.movement.export', '成品录入：导出进出明细', 'inventory_ops_finished', '成品录入', 35),
('inventory_ops_semi.movement.export', '半成品录入：导出进出明细', 'inventory_ops_semi', '半成品录入', 35),
('inventory_ops_material.movement.export', '材料录入：导出进出明细', 'inventory_ops_material', '材料录入', 35)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

-- 已有“手工出入库”权限的角色，默认追加“导出进出明细”权限
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, 'inventory_ops_finished.movement.export'
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` = 'inventory_ops_finished.movement.create';

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, 'inventory_ops_semi.movement.export'
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` = 'inventory_ops_semi.movement.create';

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, 'inventory_ops_material.movement.export'
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` = 'inventory_ops_material.movement.create';
