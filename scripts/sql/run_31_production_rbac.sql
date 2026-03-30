-- 生产管理：新增导航菜单 + 能力键；分配给仓管角色
-- 无外键约束

USE sydixon_order;
SET NAMES utf8mb4;

-- 导航节点
INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (2, 'production', '生产管理', 'main.production_preplan_list', 50, 1, 0, 1, 87)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

-- 能力键
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('production.preplan.action.create', '生产管理：预生产计划新建', 'production', '生产管理', 10),
('production.preplan.action.edit', '生产管理：预生产计划编辑', 'production', '生产管理', 20),
('production.preplan.action.delete', '生产管理：预生产计划删除', 'production', '生产管理', 30),
('production.calc.action.run', '生产管理：生产测算运行', 'production', '生产管理', 40)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

-- 角色菜单分配：仓管角色（warehouse）
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'production'
FROM `role` r
WHERE r.`code`='warehouse';

