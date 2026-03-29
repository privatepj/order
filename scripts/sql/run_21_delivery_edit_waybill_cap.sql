-- 能力键 delivery.action.edit_waybill（列表修改快递单号）
-- 执行后若后台「角色」页仍看不到新细项：应用进程内 RBAC 缓存需刷新——重启 Web 进程，
-- 或拉取含「打开 /system/capabilities 或角色编辑页时 invalidate」的代码后重新访问上述页面。
USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('delivery.action.edit_waybill', '送货：修改快递单号（列表）', 'delivery', '送货', 116)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`), `nav_item_code`=VALUES(`nav_item_code`), `group_label`=VALUES(`group_label`), `sort_order`=VALUES(`sort_order`);

-- 可选：与「修改送货单号」权限一致的角色自动获得本能力（不需要则注释掉以下段落）
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT `role_id`, 'delivery.action.edit_waybill'
FROM `role_allowed_capability`
WHERE `cap_code` = 'delivery.action.edit_delivery_no';
