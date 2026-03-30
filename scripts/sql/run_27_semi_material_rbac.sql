-- 半成品/物料主数据：新增导航菜单 + 能力键 + 给仓管角色分配
-- 无外键约束

USE sydixon_order;
SET NAMES utf8mb4;

-- 导航节点
INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (7, 'semi_material', '半成品/物料', 'main.semi_material_list', 25, 1, 0, 1, 88)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

-- 能力键
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('semi_material.filter.keyword', '半成品/物料列表：关键词搜索', 'semi_material', '半成品/物料', 10),
('semi_material.action.create', '半成品/物料：新建主数据', 'semi_material', '半成品/物料', 20),
('semi_material.action.edit', '半成品/物料：编辑主数据', 'semi_material', '半成品/物料', 30),
('semi_material.action.delete', '半成品/物料：删除主数据', 'semi_material', '半成品/物料', 40),
('semi_material.action.import', '半成品/物料：Excel 导入', 'semi_material', '半成品/物料', 50)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

-- 角色菜单分配：仓管角色（warehouse）
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'semi_material'
FROM `role` r
WHERE r.`code`='warehouse';

