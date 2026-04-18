-- 库存录入行「当前结存」接口能力：三类库存录入菜单新增 api.movement_line_on_hand
USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('inventory_ops_finished.api.movement_line_on_hand', '成品录入：录入行当前结存接口', 'inventory_ops_finished', '成品录入', 21),
('inventory_ops_semi.api.movement_line_on_hand', '半成品录入：录入行当前结存接口', 'inventory_ops_semi', '半成品录入', 21),
('inventory_ops_material.api.movement_line_on_hand', '材料录入：录入行当前结存接口', 'inventory_ops_material', '材料录入', 21)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

-- 已有「手工出入库」权限的角色，默认追加「录入行当前结存接口」权限
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, 'inventory_ops_finished.api.movement_line_on_hand'
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` = 'inventory_ops_finished.movement.create';

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, 'inventory_ops_semi.api.movement_line_on_hand'
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` = 'inventory_ops_semi.movement.create';

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, 'inventory_ops_material.api.movement_line_on_hand'
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` = 'inventory_ops_material.movement.create';
