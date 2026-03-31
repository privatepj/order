-- 快递：单号池批量删除（express.action.waybill_batch_delete）
-- 若后台「角色」页/菜单权限已缓存：重启 Web 进程或清理 RBAC 缓存后再生效。

USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('express.action.waybill_batch_delete', '快递：单号池批量删除', 'express', '快递', 35)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

-- 可选：与「单号池导入」权限保持一致（若角色显式授权了导入，则自动获得批量删除）
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT `role_id`, 'express.action.waybill_batch_delete'
FROM `role_allowed_capability`
WHERE `cap_code` = 'express.action.waybill_import';

