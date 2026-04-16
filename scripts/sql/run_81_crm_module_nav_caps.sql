-- CRM 模块：导航菜单项 + 细项能力（无 FOREIGN KEY）
USE sydixon_order;
SET NAMES utf8mb4;

-- nav_base 节点
SET @nav_base_id = (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_base' LIMIT 1);

-- CRM 导航叶子
INSERT INTO `sys_nav_item` (`parent_id`, `code`, `title`, `endpoint`, `sort_order`, `is_active`, `admin_only`, `is_assignable`, `landing_priority`)
VALUES
(@nav_base_id, 'crm_lead', 'CRM 线索', 'main.crm_lead_list', 45, 1, 0, 1, NULL),
(@nav_base_id, 'crm_opportunity', 'CRM 机会', 'main.crm_opportunity_list', 46, 1, 0, 1, NULL),
(@nav_base_id, 'crm_ticket', 'CRM 工单', 'main.crm_ticket_list', 47, 1, 0, 1, NULL)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

-- CRM 细项能力
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`)
VALUES
('crm_lead.action.create', 'CRM 线索：新建', 'crm_lead', 'CRM', 10),
('crm_lead.action.edit', 'CRM 线索：编辑', 'crm_lead', 'CRM', 20),
('crm_lead.action.delete', 'CRM 线索：删除', 'crm_lead', 'CRM', 30),

('crm_opportunity.action.create', 'CRM 机会：新建', 'crm_opportunity', 'CRM', 10),
('crm_opportunity.action.edit', 'CRM 机会：编辑', 'crm_opportunity', 'CRM', 20),
('crm_opportunity.action.generate_order', 'CRM 机会：生成订单', 'crm_opportunity', 'CRM', 30),

('crm_ticket.action.create', 'CRM 工单：新建', 'crm_ticket', 'CRM', 10),
('crm_ticket.action.edit', 'CRM 工单：编辑', 'crm_ticket', 'CRM', 20),
('crm_ticket.action.delete', 'CRM 工单：删除', 'crm_ticket', 'CRM', 30)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

-- 让销售/仓管角色默认可看到 CRM 菜单（明细能力仍需 capability keys 或 admin）
INSERT INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.id, x.nav_code
FROM `role` r
JOIN (
  SELECT 'crm_lead' AS nav_code
  UNION ALL SELECT 'crm_opportunity'
  UNION ALL SELECT 'crm_ticket'
) x
WHERE r.code IN ('sales', 'warehouse')
ON DUPLICATE KEY UPDATE `nav_code`=VALUES(`nav_code`);

