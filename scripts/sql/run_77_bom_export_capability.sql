-- BOM 管理：新增多级 Excel 导出能力
-- 无外键约束

USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('bom.action.export', 'BOM：Excel 导出', 'bom', 'BOM', 60)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

-- 已有 BOM 导入权限的角色，默认补齐导出权限
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT `role_id`, 'bom.action.export'
FROM `role_allowed_capability`
WHERE `cap_code` = 'bom.action.import';
