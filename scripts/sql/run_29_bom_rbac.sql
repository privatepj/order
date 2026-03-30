-- BOM 管理：新增导航菜单 + 能力键 + 给仓管角色分配
-- 无外键约束

USE sydixon_order;
SET NAMES utf8mb4;

-- 导航节点
INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (7, 'bom', 'BOM 管理', 'main.bom_list', 26, 1, 0, 1, 89)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

-- 能力键
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('bom.filter.keyword', 'BOM 列表：关键词搜索', 'bom', 'BOM', 10),
('bom.action.create', 'BOM：新建', 'bom', 'BOM', 20),
('bom.action.edit', 'BOM：编辑', 'bom', 'BOM', 30),
('bom.action.delete', 'BOM：删除', 'bom', 'BOM', 40),
('bom.action.import', 'BOM：Excel 导入', 'bom', 'BOM', 50)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

-- 角色菜单分配：仓管角色（warehouse）
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'bom'
FROM `role` r
WHERE r.`code`='warehouse';

