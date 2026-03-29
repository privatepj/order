-- 工厂订单系统 - 增量迁移脚本（仅用于从旧版本库升级）
-- 新库部署请勿执行本文件，只执行 00_full_schema.sql。
-- 执行前请备份数据库。若某条语句报「Duplicate column」等已存在错误，可忽略继续。

USE sydixon_order;
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ========== 1. 经营主体与客户 v2 ==========
CREATE TABLE IF NOT EXISTS `company` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '主体名称',
  `code` varchar(32) NOT NULL COMMENT '短码',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='经营主体';

INSERT INTO `company` (`name`, `code`)
SELECT '经营主体A', 'A' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `company` WHERE `code` = 'A');
INSERT INTO `company` (`name`, `code`)
SELECT '经营主体B', 'B' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `company` WHERE `code` = 'B');

ALTER TABLE `customer`
  ADD COLUMN `company_id` int unsigned NULL COMMENT '经营主体' AFTER `remark`,
  ADD COLUMN `tax_point` decimal(6,4) DEFAULT NULL COMMENT '税率如0.13' AFTER `company_id`;

UPDATE `customer` c SET `company_id` = (SELECT MIN(id) FROM `company`) WHERE c.`company_id` IS NULL;

ALTER TABLE `customer`
  MODIFY `company_id` int unsigned NOT NULL,
  ADD KEY `idx_company_id` (`company_id`);

ALTER TABLE `customer_product`
  ADD COLUMN `material_no` varchar(64) DEFAULT NULL COMMENT '物料编号' AFTER `customer_material_no`;

-- ========== 2. 公司订单号前缀与转月日 ==========
ALTER TABLE `company`
  ADD COLUMN `order_no_prefix` varchar(32) DEFAULT NULL COMMENT '订单号前缀' AFTER `code`,
  ADD COLUMN `billing_cycle_day` tinyint unsigned NOT NULL DEFAULT 1 COMMENT '转月日(1-31,1=自然月)' AFTER `order_no_prefix`;

UPDATE `company` SET `order_no_prefix` = `code` WHERE `order_no_prefix` IS NULL OR `order_no_prefix` = '';

-- ========== 3. 客户传真、经营主体联系信息 ==========
ALTER TABLE `customer`
  ADD COLUMN `fax` varchar(32) DEFAULT NULL COMMENT '传真' AFTER `phone`;

ALTER TABLE `company`
  ADD COLUMN `delivery_no_prefix` varchar(32) DEFAULT NULL COMMENT '送货单号前缀' AFTER `order_no_prefix`;

ALTER TABLE `company`
  ADD COLUMN `phone` varchar(32) DEFAULT NULL COMMENT '电话' AFTER `billing_cycle_day`;

ALTER TABLE `company`
  ADD COLUMN `fax` varchar(32) DEFAULT NULL COMMENT '传真' AFTER `phone`;

ALTER TABLE `company`
  ADD COLUMN `address` varchar(255) DEFAULT NULL COMMENT '地址' AFTER `fax`;

ALTER TABLE `company`
  ADD COLUMN `contact_person` varchar(64) DEFAULT NULL COMMENT '联系人' AFTER `address`;

ALTER TABLE `company`
  ADD COLUMN `private_account` varchar(64) DEFAULT NULL COMMENT '对私账户' AFTER `contact_person`;

ALTER TABLE `company`
  ADD COLUMN `public_account` varchar(64) DEFAULT NULL COMMENT '对公账户' AFTER `private_account`;

ALTER TABLE `company`
  ADD COLUMN `account_name` varchar(64) DEFAULT NULL COMMENT '户名' AFTER `public_account`;

ALTER TABLE `company`
  ADD COLUMN `bank_name` varchar(128) DEFAULT NULL COMMENT '开户行' AFTER `account_name`;

ALTER TABLE `company`
  ADD COLUMN `preparer_name` varchar(64) DEFAULT NULL COMMENT '对账制表人' AFTER `bank_name`;

-- ========== 4. 快递公司、单号池、送货单扩展 ==========
UPDATE `company` SET `delivery_no_prefix` = `code` WHERE `delivery_no_prefix` IS NULL;

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

INSERT IGNORE INTO `express_company` (`id`, `name`, `code`, `is_active`) VALUES (1, '历史数据（无快递单号）', 'LEGACY', 1);

ALTER TABLE `delivery`
  ADD COLUMN `express_company_id` int unsigned DEFAULT NULL AFTER `customer_id`,
  ADD COLUMN `express_waybill_id` int unsigned DEFAULT NULL AFTER `express_company_id`,
  ADD COLUMN `waybill_no` varchar(64) DEFAULT NULL AFTER `express_waybill_id`;

UPDATE `delivery` SET `express_company_id` = 1 WHERE `express_company_id` IS NULL;

ALTER TABLE `delivery`
  MODIFY `express_company_id` int unsigned NOT NULL,
  ADD KEY `idx_express_company_id` (`express_company_id`);

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

-- ========== 5. 用户申请角色 ==========
ALTER TABLE `user`
  ADD COLUMN `requested_role_id` int unsigned NULL AFTER `role_id`;

ALTER TABLE `user`
  ADD KEY `idx_requested_role_id` (`requested_role_id`);

-- ========== 6. 待分配角色 ==========
INSERT INTO `role` (`name`, `code`, `description`)
SELECT '待分配', 'pending', '注册后等待管理员分配'
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM `role` WHERE `code` = 'pending');

-- ========== 7. 客户简称 ==========
ALTER TABLE `customer`
  ADD COLUMN `short_code` VARCHAR(32) NULL AFTER `customer_code`;

-- ========== 8. 订单明细是否样品 ==========
ALTER TABLE `order_item`
  ADD COLUMN `is_sample` TINYINT(1) NOT NULL DEFAULT 0 AFTER `amount`;

-- ========== 9. 订单付款类型 ==========
ALTER TABLE `sales_order`
  ADD COLUMN `payment_type` varchar(16) NOT NULL DEFAULT 'monthly'
  COMMENT 'monthly=月结 cash=现金 sample=样板' AFTER `status`;

-- ========== 10. 角色可访问菜单 ==========
ALTER TABLE `role`
  ADD COLUMN `allowed_menu_keys` json DEFAULT NULL COMMENT '可访问菜单 key 的 JSON 数组' AFTER `description`;

UPDATE `role` SET `allowed_menu_keys` = CAST('["order","delivery","customer","product","customer_product","reconciliation"]' AS JSON)
WHERE `code` IN ('sales', 'warehouse', 'finance');

UPDATE `role` SET `allowed_menu_keys` = CAST('[]' AS JSON) WHERE `code` = 'pending';

-- ========== 11. 接口审计日志表 ==========
CREATE TABLE IF NOT EXISTS `audit_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `event_type` varchar(16) NOT NULL,
  `method` varchar(8) DEFAULT NULL,
  `path` varchar(512) NOT NULL,
  `query_string` varchar(2048) DEFAULT NULL,
  `status_code` smallint DEFAULT NULL,
  `duration_ms` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `auth_type` varchar(16) NOT NULL,
  `ip` varchar(45) NOT NULL,
  `user_agent` varchar(512) DEFAULT NULL,
  `endpoint` varchar(128) DEFAULT NULL,
  `extra` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_audit_log_created_at` (`created_at`),
  KEY `ix_audit_log_user_created` (`user_id`, `created_at`),
  KEY `ix_audit_log_path` (`path`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ========== 12. 每日库存录入（单仓快照） ==========
CREATE TABLE IF NOT EXISTS `inventory_daily_record` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `record_date` date NOT NULL COMMENT '业务日',
  `status` varchar(16) NOT NULL DEFAULT 'confirmed' COMMENT 'draft=草稿 confirmed=已确认',
  `remark` varchar(500) DEFAULT NULL,
  `created_by` int unsigned NOT NULL COMMENT '录入人 user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_inv_daily_record_date` (`record_date`),
  KEY `idx_inv_daily_created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日库存录入主表';

CREATE TABLE IF NOT EXISTS `inventory_daily_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `header_id` int unsigned NOT NULL,
  `product_id` int unsigned NOT NULL,
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `note` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inv_daily_header_product` (`header_id`,`product_id`),
  KEY `idx_inv_daily_line_header` (`header_id`),
  KEY `idx_inv_daily_line_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日库存明细';

UPDATE `role` SET `allowed_menu_keys` = CAST('["order","delivery","express","inventory","customer","product","customer_product","reconciliation"]' AS JSON)
WHERE `code` = 'warehouse';

-- ========== 13. 库存期初与进出明细 ==========
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

-- ========== 角色细项能力（按钮、筛选项）==========
ALTER TABLE `role`
  ADD COLUMN `allowed_capability_keys` json DEFAULT NULL COMMENT '细项能力 key；NULL/[] 表示在已选菜单内默认全开' AFTER `allowed_menu_keys`;

-- ========== 导航与 RBAC（菜单/能力库表化）==========
-- 亦可单独执行：run_15_nav_rbac_schema.sql、run_16_seed_nav_capability.sql、run_17_migrate_role_json_to_nav_cap.sql

CREATE TABLE IF NOT EXISTS `sys_nav_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `parent_id` int unsigned DEFAULT NULL,
  `code` varchar(64) NOT NULL,
  `title` varchar(128) NOT NULL,
  `endpoint` varchar(128) DEFAULT NULL,
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `admin_only` tinyint(1) NOT NULL DEFAULT 0,
  `is_assignable` tinyint(1) NOT NULL DEFAULT 1,
  `landing_priority` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_nav_code` (`code`),
  KEY `idx_nav_parent` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='导航菜单项';

CREATE TABLE IF NOT EXISTS `sys_capability` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `code` varchar(128) NOT NULL,
  `title` varchar(255) NOT NULL,
  `nav_item_code` varchar(64) NOT NULL,
  `group_label` varchar(128) NOT NULL DEFAULT '',
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cap_code` (`code`),
  KEY `idx_cap_nav` (`nav_item_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='细项能力';

CREATE TABLE IF NOT EXISTS `role_allowed_nav` (
  `role_id` int unsigned NOT NULL,
  `nav_code` varchar(64) NOT NULL,
  PRIMARY KEY (`role_id`, `nav_code`),
  KEY `idx_ran_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色可访问菜单';

CREATE TABLE IF NOT EXISTS `role_allowed_capability` (
  `role_id` int unsigned NOT NULL,
  `cap_code` varchar(128) NOT NULL,
  PRIMARY KEY (`role_id`, `cap_code`),
  KEY `idx_rac_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色显式细项能力';

-- ========== 送货单：自配送时 express_company 可空 ==========
-- 亦可单独执行：run_19_delivery_express_nullable.sql
ALTER TABLE `delivery`
  MODIFY COLUMN `express_company_id` int unsigned DEFAULT NULL COMMENT '快递公司；NULL 表示自配送';

SET FOREIGN_KEY_CHECKS = 1;
