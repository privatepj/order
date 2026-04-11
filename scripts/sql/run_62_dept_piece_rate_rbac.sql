-- 工种计件单价管理：导航 + 能力 + 财务角色菜单
-- 为 dept_piece_rate 功能添加 RBAC 权限

USE sydixon_order;
SET NAMES utf8mb4;

-- 获取 nav_hr 的 id
SET @nav_hr_id = (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_hr' LIMIT 1);

-- 新增导航项：工种计件单价
INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_hr_id, 'dept_piece_rate', '工种计件单价', 'main.dept_piece_rate_list', 35, 1, 0, 1, 96)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

-- 新增能力项
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('dept_piece_rate.view', '工种计件单价：查看', 'dept_piece_rate', '人力资源', 450),
('dept_piece_rate.edit', '工种计件单价：编辑与删除', 'dept_piece_rate', '人力资源', 460)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

-- 为 finance 角色分配导航权限
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'dept_piece_rate' FROM `role` r WHERE r.`code`='finance';

-- 为 finance 角色分配能力权限
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, 'dept_piece_rate.view' FROM `role` r WHERE r.`code`='finance';
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, 'dept_piece_rate.edit' FROM `role` r WHERE r.`code`='finance';
