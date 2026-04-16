-- 预生产计划：测算成本仅对有细项能力的角色可见（默认不批量授予角色，由管理员在角色页分配）
-- 无外键约束

USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('production.preplan.cost.view', '预生产计划：查看测算成本', 'production_preplan', '预生产计划', 45)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);
