-- 成品/半成品主数据「系列」；库存查询筛选能力
USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `product`
  ADD COLUMN `series` varchar(64) DEFAULT NULL COMMENT '系列' AFTER `spec`;

ALTER TABLE `semi_material`
  ADD COLUMN `series` varchar(64) DEFAULT NULL COMMENT '系列' AFTER `spec`;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('inventory_query.filter.series', '库存查询：系列', 'inventory_query', '库存查询', 25)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

-- 已有「库存查询：类别」筛选权限的角色，默认追加「系列」筛选
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT rac.`role_id`, 'inventory_query.filter.series'
FROM `role_allowed_capability` rac
WHERE rac.`cap_code` = 'inventory_query.filter.category';
