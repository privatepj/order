-- 单次执行：库存台账表（无 product.model）
-- 若表已存在，请按报错跳过对应语句

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `inventory_opening_balance` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL COMMENT 'finished=成品 semi=半成品',
  `product_id` int unsigned NOT NULL DEFAULT 0,
  `material_id` int unsigned NOT NULL DEFAULT 0,
  `storage_area` varchar(32) NOT NULL DEFAULT '' COMMENT '仓储区',
  `opening_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inv_opening_bucket` (`category`,`product_id`,`material_id`,`storage_area`),
  KEY `idx_inv_opening_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存期初结存';

CREATE TABLE IF NOT EXISTS `inventory_movement` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL,
  `direction` varchar(8) NOT NULL COMMENT 'in=入库 out=出库',
  `product_id` int unsigned NOT NULL DEFAULT 0,
  `material_id` int unsigned NOT NULL DEFAULT 0,
  `storage_area` varchar(32) NOT NULL DEFAULT '',
  `quantity` decimal(18,4) NOT NULL,
  `unit` varchar(16) DEFAULT NULL,
  `biz_date` date NOT NULL,
  `source_type` varchar(16) NOT NULL DEFAULT 'manual',
  `source_delivery_id` int unsigned DEFAULT NULL,
  `source_delivery_item_id` int unsigned DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inv_mov_delivery_item` (`source_delivery_item_id`),
  KEY `idx_inv_mov_delivery` (`source_delivery_id`),
  KEY `idx_inv_mov_product_area` (`product_id`,`storage_area`),
  KEY `idx_inv_mov_biz_date` (`biz_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存进出明细';
