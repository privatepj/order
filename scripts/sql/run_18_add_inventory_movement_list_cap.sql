-- 补充能力键 inventory_ops.movement.list（已并入 run_16 / 00_full_schema；仅旧库曾执行过早期 run_16 时补跑）
USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('inventory_ops.movement.list', '库存录入：库存批次列表', 'inventory_ops', '库存录入', 25)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`), `nav_item_code`=VALUES(`nav_item_code`), `group_label`=VALUES(`group_label`), `sort_order`=VALUES(`sort_order`);
