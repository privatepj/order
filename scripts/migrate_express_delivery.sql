-- 已有库升级：快递公司、单号池、送货单扩展、主体送货前缀
-- 执行前请备份数据库

USE sydixon_order;

SET FOREIGN_KEY_CHECKS = 0;

-- 主体：送货单号前缀
ALTER TABLE `company`
  ADD COLUMN `delivery_no_prefix` varchar(32) DEFAULT NULL COMMENT '送货单号前缀' AFTER `order_no_prefix`;

UPDATE `company` SET `delivery_no_prefix` = `code` WHERE `delivery_no_prefix` IS NULL;

-- 快递公司
CREATE TABLE IF NOT EXISTS `express_company` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '快递公司名称',
  `code` varchar(32) NOT NULL COMMENT '短码',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_express_company_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='快递公司';

INSERT IGNORE INTO `express_company` (`id`, `name`, `code`, `is_active`) VALUES
(1, '历史数据（无快递单号）', 'LEGACY', 1);

-- 送货单扩展列（在创建 express_waybill 之前）
ALTER TABLE `delivery`
  ADD COLUMN `express_company_id` int unsigned DEFAULT NULL AFTER `customer_id`,
  ADD COLUMN `express_waybill_id` int unsigned DEFAULT NULL AFTER `express_company_id`,
  ADD COLUMN `waybill_no` varchar(64) DEFAULT NULL AFTER `express_waybill_id`;

UPDATE `delivery` SET `express_company_id` = 1 WHERE `express_company_id` IS NULL;

ALTER TABLE `delivery`
  MODIFY `express_company_id` int unsigned NOT NULL,
  ADD KEY `idx_express_company_id` (`express_company_id`);

-- 快递单号池
CREATE TABLE IF NOT EXISTS `express_waybill` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `express_company_id` int unsigned NOT NULL,
  `waybill_no` varchar(64) NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'available' COMMENT 'available/used',
  `delivery_id` int unsigned DEFAULT NULL,
  `used_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_waybill` (`express_company_id`, `waybill_no`),
  KEY `idx_available` (`express_company_id`, `status`, `id`),
  KEY `idx_delivery_id` (`delivery_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='快递单号池';

SET FOREIGN_KEY_CHECKS = 1;
