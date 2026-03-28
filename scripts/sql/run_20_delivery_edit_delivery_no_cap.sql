-- 能力键 delivery.action.edit_delivery_no（旧库补跑）
USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('delivery.action.edit_delivery_no', '送货：修改送货单号（列表）', 'delivery', '送货', 115)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`), `nav_item_code`=VALUES(`nav_item_code`), `group_label`=VALUES(`group_label`), `sort_order`=VALUES(`sort_order`);
