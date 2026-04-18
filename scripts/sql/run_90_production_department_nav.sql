-- 生产管理：部门生产看板菜单 + 细项能力（无 FOREIGN KEY）
USE sydixon_order;
SET NAMES utf8mb4;

SET @production_nav_id := (
  SELECT `id` FROM `sys_nav_item` WHERE `code` = 'production' LIMIT 1
);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
)
VALUES (
  @production_nav_id,
  'production_department',
  '部门生产看板',
  'main.production_department_board',
  15,
  1, 0, 1, NULL
)
ON DUPLICATE KEY UPDATE
  `parent_id` = VALUES(`parent_id`),
  `title` = VALUES(`title`),
  `endpoint` = VALUES(`endpoint`),
  `sort_order` = VALUES(`sort_order`),
  `admin_only` = VALUES(`admin_only`),
  `is_assignable` = VALUES(`is_assignable`),
  `landing_priority` = VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('production.department.board.view', '部门生产看板：查看', 'production_department', '部门生产看板', 10),
('production.department.board.filter_dept', '部门生产看板：切换部门', 'production_department', '部门生产看板', 20)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

-- 已具备「预生产计划」菜单的角色，同步开放部门看板（细项能力仍按角色白名单）
INSERT INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.id, 'production_department'
FROM `role` r
INNER JOIN `role_allowed_nav` ran ON ran.role_id = r.id AND ran.nav_code = 'production_preplan'
ON DUPLICATE KEY UPDATE `nav_code` = VALUES(`nav_code`);
