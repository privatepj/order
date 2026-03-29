-- OpenClaw：用户 API 令牌表 + 专用能力键（可重复执行）
USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `user_api_token` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `token_hash` char(64) NOT NULL COMMENT 'SHA256 十六进制',
  `label` varchar(128) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expires_at` datetime DEFAULT NULL,
  `revoked_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_token_hash` (`token_hash`),
  KEY `idx_user_api_token_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户 API 令牌（OpenClaw 等）';

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('openclaw.customers.read', 'OpenClaw：客户列表', 'customer', 'OpenClaw', 5),
('openclaw.customer_products.read', 'OpenClaw：客户产品列表', 'customer_product', 'OpenClaw', 6),
('openclaw.pending_items.read', 'OpenClaw：待发货明细', 'delivery', 'OpenClaw', 7),
('openclaw.order.create', 'OpenClaw：创建订单', 'order', 'OpenClaw', 8),
('openclaw.delivery.create', 'OpenClaw：创建送货单', 'delivery', 'OpenClaw', 9)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);
