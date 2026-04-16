-- CRM 模块：从 nav_base 分组中拆出为独立大菜单 nav_crm（无 FOREIGN KEY）
USE sydixon_order;
SET NAMES utf8mb4;

-- 1) 新建/补齐 CRM 分组根节点
INSERT INTO `sys_nav_item` (
  `parent_id`,
  `code`,
  `title`,
  `endpoint`,
  `sort_order`,
  `is_active`,
  `admin_only`,
  `is_assignable`,
  `landing_priority`
)
VALUES
  (NULL, 'nav_crm', 'CRM管理', NULL, 25, 1, 0, 0, NULL)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `sort_order`=VALUES(`sort_order`),
  `is_active`=VALUES(`is_active`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

-- 2) 将 CRM 叶子移到 nav_crm
SET @nav_crm_id = (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_crm' LIMIT 1);

UPDATE `sys_nav_item`
SET `parent_id` = @nav_crm_id
WHERE `code` IN ('crm_lead', 'crm_opportunity', 'crm_ticket');

