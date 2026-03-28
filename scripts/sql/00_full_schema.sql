-- 工厂订单系统 - 全量建表脚本（新库部署用）
-- 使用前请先创建数据库: CREATE DATABASE IF NOT EXISTS sydixon_order DEFAULT CHARSET utf8mb4;
-- 新服务器部署只需执行本文件即可，无需再执行其他 SQL。
-- 本脚本不创建数据库级 FOREIGN KEY；表间引用由应用层逻辑保证，与 ORM 中 primaryjoin/foreign() 一致。

USE sydixon_order;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 角色表
-- ----------------------------
DROP TABLE IF EXISTS `role`;
CREATE TABLE `role` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(64) NOT NULL COMMENT '角色名称',
  `code` varchar(32) NOT NULL COMMENT '角色代码 admin/sales/warehouse/finance',
  `description` varchar(255) DEFAULT NULL,
  `allowed_menu_keys` json DEFAULT NULL COMMENT '可访问菜单 key 的 JSON 数组',
  `allowed_capability_keys` json DEFAULT NULL COMMENT '细项能力 key；NULL/[] 表示在已选菜单内默认全开',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色表';

-- ----------------------------
-- 用户表
-- ----------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(64) NOT NULL COMMENT '登录名',
  `password_hash` varchar(255) NOT NULL,
  `name` varchar(64) DEFAULT NULL COMMENT '姓名',
  `role_id` int unsigned NOT NULL,
  `requested_role_id` int unsigned DEFAULT NULL COMMENT '申请的目标角色',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  KEY `idx_role_id` (`role_id`),
  KEY `idx_requested_role_id` (`requested_role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- ----------------------------
-- 经营主体（先删依赖客户的表）
-- ----------------------------
DROP TABLE IF EXISTS `customer_product`;
DROP TABLE IF EXISTS `customer`;
DROP TABLE IF EXISTS `company`;
CREATE TABLE `company` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '主体名称',
  `code` varchar(32) NOT NULL COMMENT '短码',
  `order_no_prefix` varchar(32) DEFAULT NULL COMMENT '订单号前缀',
  `delivery_no_prefix` varchar(32) DEFAULT NULL COMMENT '送货单号前缀',
  `billing_cycle_day` tinyint unsigned NOT NULL DEFAULT 1 COMMENT '转月日/月结日',
  `phone` varchar(32) DEFAULT NULL COMMENT '电话',
  `fax` varchar(32) DEFAULT NULL COMMENT '传真',
  `address` varchar(255) DEFAULT NULL COMMENT '地址',
  `contact_person` varchar(64) DEFAULT NULL COMMENT '联系人',
  `private_account` varchar(64) DEFAULT NULL COMMENT '对私账户',
  `public_account` varchar(64) DEFAULT NULL COMMENT '对公账户',
  `account_name` varchar(64) DEFAULT NULL COMMENT '户名',
  `bank_name` varchar(128) DEFAULT NULL COMMENT '开户行',
  `preparer_name` varchar(64) DEFAULT NULL COMMENT '对账制表人',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='经营主体';

INSERT INTO `company` (`name`, `code`, `order_no_prefix`, `delivery_no_prefix`, `billing_cycle_day`) VALUES
('经营主体A', 'A', 'A', 'A', 1),
('经营主体B', 'B', 'B', 'B', 1);

-- ----------------------------
-- 客户表
-- ----------------------------
CREATE TABLE `customer` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `customer_code` varchar(64) NOT NULL COMMENT '客户编码',
  `short_code` varchar(32) DEFAULT NULL COMMENT '客户简称',
  `name` varchar(128) NOT NULL COMMENT '客户名称',
  `contact` varchar(64) DEFAULT NULL,
  `phone` varchar(32) DEFAULT NULL,
  `fax` varchar(32) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `payment_terms` varchar(64) DEFAULT NULL COMMENT '结算方式',
  `remark` varchar(255) DEFAULT NULL,
  `company_id` int unsigned NOT NULL COMMENT '经营主体',
  `tax_point` decimal(6,4) DEFAULT NULL COMMENT '税率小数如0.13',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_customer_code` (`customer_code`),
  KEY `idx_company_id` (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户表';

-- ----------------------------
-- 产品主数据表
-- ----------------------------
DROP TABLE IF EXISTS `product`;
CREATE TABLE `product` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `product_code` varchar(64) NOT NULL COMMENT '内部物料编号',
  `name` varchar(128) NOT NULL COMMENT '产品名称',
  `spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `base_unit` varchar(16) DEFAULT NULL COMMENT '基础单位',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_product_code` (`product_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品主数据';

-- ----------------------------
-- 客户产品表
-- ----------------------------
CREATE TABLE `customer_product` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `customer_id` int unsigned NOT NULL,
  `product_id` int unsigned NOT NULL,
  `customer_material_no` varchar(64) DEFAULT NULL COMMENT '客户料号',
  `material_no` varchar(64) DEFAULT NULL COMMENT '物料编号',
  `unit` varchar(16) DEFAULT NULL COMMENT '结算单位',
  `price` decimal(18,4) DEFAULT NULL COMMENT '单价',
  `currency` varchar(8) DEFAULT NULL COMMENT '币种',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_customer_id` (`customer_id`),
  KEY `idx_product_id` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户产品映射';

-- ----------------------------
-- 订单表头
-- ----------------------------
DROP TABLE IF EXISTS `order_item`;
DROP TABLE IF EXISTS `sales_order`;
CREATE TABLE `sales_order` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `order_no` varchar(64) NOT NULL COMMENT '我方订单编号',
  `customer_order_no` varchar(64) DEFAULT NULL COMMENT '客户订单编号',
  `customer_id` int unsigned NOT NULL,
  `salesperson` varchar(64) NOT NULL DEFAULT 'GaoMeiHua' COMMENT '销售人',
  `order_date` date DEFAULT NULL,
  `required_date` date DEFAULT NULL COMMENT '要求交货日',
  `status` varchar(32) NOT NULL DEFAULT 'pending' COMMENT 'pending/partial/delivered/closed',
  `payment_type` varchar(16) NOT NULL DEFAULT 'monthly' COMMENT 'monthly/cash/sample',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_no` (`order_no`),
  KEY `idx_customer_id` (`customer_id`),
  KEY `idx_customer_order_no` (`customer_order_no`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表头';

-- ----------------------------
-- 订单明细
-- ----------------------------
CREATE TABLE `order_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `order_id` int unsigned NOT NULL,
  `customer_product_id` int unsigned DEFAULT NULL COMMENT '来源客户产品表',
  `product_name` varchar(128) DEFAULT NULL COMMENT '品名',
  `product_spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `customer_material_no` varchar(64) DEFAULT NULL COMMENT '客户料号',
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `price` decimal(18,4) DEFAULT NULL,
  `amount` decimal(18,2) DEFAULT NULL COMMENT '该行总金额',
  `is_sample` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否样品',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_order_id` (`order_id`),
  KEY `idx_customer_product_id` (`customer_product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细';

-- ----------------------------
-- 快递公司
-- ----------------------------
DROP TABLE IF EXISTS `express_waybill`;
DROP TABLE IF EXISTS `delivery_item`;
DROP TABLE IF EXISTS `delivery`;
DROP TABLE IF EXISTS `express_company`;
CREATE TABLE `express_company` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '快递公司名称',
  `code` varchar(32) NOT NULL COMMENT '短码',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_express_company_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='快递公司';

INSERT INTO `express_company` (`name`, `code`, `is_active`) VALUES
('顺丰速运', 'SF', 1),
('其他快递', 'OTHER', 1);

-- ----------------------------
-- 送货单头
-- ----------------------------
CREATE TABLE `delivery` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `delivery_no` varchar(64) NOT NULL COMMENT '送货单号',
  `delivery_date` date NOT NULL,
  `customer_id` int unsigned NOT NULL,
  `express_company_id` int unsigned DEFAULT NULL COMMENT '快递公司；NULL 表示自配送',
  `express_waybill_id` int unsigned DEFAULT NULL COMMENT '占用的快递单号行',
  `waybill_no` varchar(64) DEFAULT NULL COMMENT '快递单号',
  `status` varchar(32) NOT NULL DEFAULT 'created' COMMENT 'created/shipped/signed',
  `driver` varchar(64) DEFAULT NULL,
  `plate_no` varchar(32) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_delivery_no` (`delivery_no`),
  KEY `idx_customer_id` (`customer_id`),
  KEY `idx_delivery_date` (`delivery_date`),
  KEY `idx_express_company_id` (`express_company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='送货单头';

-- ----------------------------
-- 快递单号池
-- ----------------------------
CREATE TABLE `express_waybill` (
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

-- ----------------------------
-- 送货明细
-- ----------------------------
CREATE TABLE `delivery_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `delivery_id` int unsigned NOT NULL,
  `order_item_id` int unsigned NOT NULL,
  `order_id` int unsigned NOT NULL COMMENT '冗余便于汇总',
  `product_name` varchar(128) DEFAULT NULL,
  `customer_material_no` varchar(64) DEFAULT NULL,
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_delivery_id` (`delivery_id`),
  KEY `idx_order_item_id` (`order_item_id`),
  KEY `idx_order_id` (`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='送货明细';

-- ----------------------------
-- 每日库存录入（单仓快照；多仓可后续加 warehouse 表与 warehouse_id）
-- ----------------------------
DROP TABLE IF EXISTS `inventory_daily_line`;
DROP TABLE IF EXISTS `inventory_daily_record`;
CREATE TABLE `inventory_daily_record` (
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

CREATE TABLE `inventory_daily_line` (
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

-- ----------------------------
-- 期初结存 + 进出明细台账（与 Excel 主表逻辑一致；收发由明细汇总）
-- ----------------------------
DROP TABLE IF EXISTS `inventory_movement`;
DROP TABLE IF EXISTS `inventory_opening_balance`;
CREATE TABLE `inventory_opening_balance` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL COMMENT 'finished=成品 semi=半成品',
  `product_id` int unsigned NOT NULL DEFAULT 0 COMMENT '成品时关联 product.id，0=无',
  `material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '半成品预留，0=无',
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

CREATE TABLE `inventory_movement` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL COMMENT 'finished / semi',
  `direction` varchar(8) NOT NULL COMMENT 'in=入库 out=出库',
  `product_id` int unsigned NOT NULL DEFAULT 0,
  `material_id` int unsigned NOT NULL DEFAULT 0,
  `storage_area` varchar(32) NOT NULL DEFAULT '',
  `quantity` decimal(18,4) NOT NULL,
  `unit` varchar(16) DEFAULT NULL,
  `biz_date` date NOT NULL COMMENT '业务日期',
  `source_type` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual / delivery',
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

-- ----------------------------
-- 接口审计日志
-- ----------------------------
DROP TABLE IF EXISTS `audit_log`;
CREATE TABLE `audit_log` (
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

-- ----------------------------
-- 导航与细项能力（RBAC 库表，与 run_15/run_16 一致）
-- ----------------------------
DROP TABLE IF EXISTS `role_allowed_capability`;
DROP TABLE IF EXISTS `role_allowed_nav`;
DROP TABLE IF EXISTS `sys_capability`;
DROP TABLE IF EXISTS `sys_nav_item`;

CREATE TABLE `sys_nav_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `parent_id` int unsigned DEFAULT NULL,
  `code` varchar(64) NOT NULL,
  `title` varchar(128) NOT NULL,
  `endpoint` varchar(128) DEFAULT NULL COMMENT 'Flask endpoint，如 main.order_list',
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `admin_only` tinyint(1) NOT NULL DEFAULT 0 COMMENT '仅 admin 角色可分配',
  `is_assignable` tinyint(1) NOT NULL DEFAULT 1 COMMENT '0=仅导航分组节点',
  `landing_priority` int DEFAULT NULL COMMENT '越小越优先作为登录落地页',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_nav_code` (`code`),
  KEY `idx_nav_parent` (`parent_id`),
  CONSTRAINT `fk_nav_parent` FOREIGN KEY (`parent_id`) REFERENCES `sys_nav_item` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='导航菜单项';

CREATE TABLE `sys_capability` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `code` varchar(128) NOT NULL,
  `title` varchar(255) NOT NULL,
  `nav_item_code` varchar(64) NOT NULL COMMENT '归属菜单叶子 code',
  `group_label` varchar(128) NOT NULL DEFAULT '',
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cap_code` (`code`),
  KEY `idx_cap_nav` (`nav_item_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='细项能力';

CREATE TABLE `role_allowed_nav` (
  `role_id` int unsigned NOT NULL,
  `nav_code` varchar(64) NOT NULL,
  PRIMARY KEY (`role_id`, `nav_code`),
  KEY `idx_ran_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色可访问菜单';

CREATE TABLE `role_allowed_capability` (
  `role_id` int unsigned NOT NULL,
  `cap_code` varchar(128) NOT NULL,
  PRIMARY KEY (`role_id`, `cap_code`),
  KEY `idx_rac_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色显式细项能力白名单';

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- 初始数据：角色
-- ----------------------------
INSERT INTO `role` (`name`, `code`, `description`, `allowed_menu_keys`) VALUES
('管理员', 'admin', '系统管理员', NULL),
('销售', 'sales', '销售员', CAST('["order","delivery","customer","product","customer_product","reconciliation"]' AS JSON)),
('仓管', 'warehouse', '仓管员', CAST('["order","delivery","express","inventory_query","inventory_ops","customer","product","customer_product","reconciliation"]' AS JSON)),
('财务', 'finance', '财务人员', CAST('["order","delivery","customer","product","customer_product","reconciliation"]' AS JSON)),
('待分配', 'pending', '注册后等待管理员分配', CAST('[]' AS JSON));

-- ----------------------------
-- 初始数据：管理员用户 (默认密码 password，请首次登录后修改)
-- ----------------------------
INSERT INTO `user` (`username`, `password_hash`, `name`, `role_id`, `is_active`) VALUES
('admin', 'password', '管理员', 1, 1);

-- ----------------------------
-- 初始数据：导航树与能力定义（与 scripts/sql/run_16_seed_nav_capability.sql 同步）
-- ----------------------------
INSERT INTO `sys_nav_item` (`id`, `parent_id`, `code`, `title`, `endpoint`, `sort_order`, `is_active`, `admin_only`, `is_assignable`, `landing_priority`) VALUES
(1, NULL, 'order', '订单', 'main.order_list', 10, 1, 0, 1, 10),
(2, NULL, 'nav_warehouse', '仓管', NULL, 20, 1, 0, 0, NULL),
(3, 2, 'delivery', '送货', 'main.delivery_list', 10, 1, 0, 1, 20),
(4, 2, 'express', '快递', 'main.express_company_list', 20, 1, 0, 1, 80),
(5, 2, 'inventory_query', '库存查询', 'main.inventory_stock_query', 30, 1, 0, 1, 85),
(6, 2, 'inventory_ops', '库存录入', 'main.inventory_list', 40, 1, 0, 1, 86),
(7, NULL, 'nav_base', '基础数据', NULL, 30, 1, 0, 0, NULL),
(8, 7, 'customer', '客户', 'main.customer_list', 10, 1, 0, 1, 30),
(9, 7, 'product', '产品', 'main.product_list', 20, 1, 0, 1, 40),
(10, 7, 'customer_product', '客户产品', 'main.customer_product_list', 30, 1, 0, 1, 50),
(11, 7, 'company', '公司主体', 'main.company_list', 40, 1, 1, 1, 90),
(12, 7, 'user_mgmt', '用户管理', 'main.user_list', 50, 1, 1, 1, 100),
(13, 7, 'role_mgmt', '角色管理', 'main.role_list', 60, 1, 1, 1, 101),
(14, NULL, 'nav_finance', '财务', NULL, 40, 1, 0, 0, NULL),
(15, 14, 'reconciliation', '对账导出', 'main.reconciliation_export', 10, 1, 0, 1, 60),
(16, NULL, 'nav_report', '报表导出', NULL, 50, 1, 0, 0, NULL),
(17, 16, 'report_notes', '导出送货单Excel', 'main.report_export_delivery_notes', 10, 1, 0, 1, 70),
(18, 16, 'report_records', '导出送货记录Excel', 'main.report_export_delivery_records', 20, 1, 0, 1, 71);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('order.filter.customer', '订单列表：按客户筛选', 'order', '订单', 10),
('order.filter.status', '订单列表：按状态筛选', 'order', '订单', 20),
('order.filter.payment_type', '订单列表：按付款类型筛选', 'order', '订单', 30),
('order.filter.keyword', '订单列表：关键词搜索', 'order', '订单', 40),
('order.action.create', '订单：新建', 'order', '订单', 50),
('order.action.edit', '订单：编辑', 'order', '订单', 60),
('order.action.delete', '订单：删除', 'order', '订单', 70),
('customer_product.filter.customer', '客户产品列表：按客户筛选', 'customer_product', '客户产品', 10),
('customer_product.filter.keyword', '客户产品列表：关键词搜索', 'customer_product', '客户产品', 20),
('customer_product.action.create', '客户产品：新建', 'customer_product', '客户产品', 30),
('customer_product.action.edit', '客户产品：编辑', 'customer_product', '客户产品', 40),
('customer_product.action.delete', '客户产品：删除', 'customer_product', '客户产品', 50),
('customer_product.action.import', '客户产品：Excel 导入', 'customer_product', '客户产品', 60),
('customer_product.action.export_template', '客户产品：下载导入模板', 'customer_product', '客户产品', 70),
('delivery.filter.customer', '送货列表：按客户筛选', 'delivery', '送货', 10),
('delivery.filter.status', '送货列表：按状态筛选', 'delivery', '送货', 20),
('delivery.filter.keyword', '送货列表：关键词搜索', 'delivery', '送货', 30),
('delivery.action.create', '送货：新建送货单', 'delivery', '送货', 40),
('delivery.action.detail', '送货：详情', 'delivery', '送货', 50),
('delivery.action.print', '送货：打印', 'delivery', '送货', 60),
('delivery.action.mark_shipped', '送货：标记已发', 'delivery', '送货', 70),
('delivery.action.mark_created', '送货：标记待发', 'delivery', '送货', 80),
('delivery.action.mark_expired', '送货：标记失效', 'delivery', '送货', 90),
('delivery.action.delete', '送货：删除', 'delivery', '送货', 100),
('delivery.action.clear_waybill', '送货：清空快递单号', 'delivery', '送货', 110),
('delivery.action.edit_delivery_no', '送货：修改送货单号（列表）', 'delivery', '送货', 115),
('delivery.api.customers_search', '送货：客户搜索接口', 'delivery', '送货', 120),
('delivery.api.pending_items', '送货：待送明细接口', 'delivery', '送货', 130),
('delivery.api.next_waybill', '送货：取单号接口', 'delivery', '送货', 140),
('report_notes.page.view', '报表：送货单导出页', 'report_notes', '报表导出', 10),
('report_notes.export.run', '报表：执行导出送货单', 'report_notes', '报表导出', 20),
('report_records.page.view', '报表：送货记录导出页', 'report_records', '报表导出', 10),
('report_records.export.run', '报表：执行导出送货记录', 'report_records', '报表导出', 20),
('express.action.company_create', '快递：新建快递公司', 'express', '快递', 10),
('express.action.company_edit', '快递：编辑快递公司', 'express', '快递', 20),
('express.action.waybill_import', '快递：单号池导入', 'express', '快递', 30),
('inventory_query.filter.category', '库存查询：类别', 'inventory_query', '库存查询', 10),
('inventory_query.filter.spec', '库存查询：规格', 'inventory_query', '库存查询', 20),
('inventory_query.filter.name_spec', '库存查询：品名/规格/编号', 'inventory_query', '库存查询', 30),
('inventory_query.filter.storage_area', '库存查询：仓储区', 'inventory_query', '库存查询', 40),
('inventory_ops.api.products_search', '库存录入：产品搜索接口', 'inventory_ops', '库存录入', 10),
('inventory_ops.api.suggest_storage_area', '库存录入：仓储区建议接口', 'inventory_ops', '库存录入', 20),
('inventory_ops.movement.list', '库存录入：流水列表', 'inventory_ops', '库存录入', 25),
('inventory_ops.movement.create', '库存录入：手工出入库', 'inventory_ops', '库存录入', 30),
('inventory_ops.movement.delete', '库存录入：删除进出明细', 'inventory_ops', '库存录入', 40),
('inventory_ops.opening.list', '库存录入：期初列表', 'inventory_ops', '库存录入', 50),
('inventory_ops.opening.create', '库存录入：新建期初', 'inventory_ops', '库存录入', 60),
('inventory_ops.opening.edit', '库存录入：编辑期初', 'inventory_ops', '库存录入', 70),
('inventory_ops.opening.delete', '库存录入：删除期初', 'inventory_ops', '库存录入', 80),
('inventory_ops.daily.list', '库存录入：日结列表', 'inventory_ops', '库存录入', 90),
('inventory_ops.daily.create', '库存录入：新建日结', 'inventory_ops', '库存录入', 100),
('inventory_ops.daily.detail', '库存录入：日结详情', 'inventory_ops', '库存录入', 110),
('inventory_ops.daily.edit', '库存录入：编辑日结', 'inventory_ops', '库存录入', 120),
('inventory_ops.daily.delete', '库存录入：删除日结', 'inventory_ops', '库存录入', 130),
('customer.filter.keyword', '客户列表：关键词搜索', 'customer', '客户', 10),
('customer.action.create', '客户：新建', 'customer', '客户', 20),
('customer.action.edit', '客户：编辑', 'customer', '客户', 30),
('customer.action.delete', '客户：删除', 'customer', '客户', 40),
('customer.action.import', '客户：Excel 导入', 'customer', '客户', 50),
('product.filter.keyword', '产品列表：关键词搜索', 'product', '产品', 10),
('product.action.create', '产品：新建', 'product', '产品', 20),
('product.action.edit', '产品：编辑', 'product', '产品', 30),
('product.action.delete', '产品：删除', 'product', '产品', 40),
('product.action.import', '产品：Excel 导入', 'product', '产品', 50),
('company.action.create', '公司主体：新建', 'company', '公司主体', 10),
('company.action.edit', '公司主体：编辑', 'company', '公司主体', 20),
('company.action.delete', '公司主体：删除', 'company', '公司主体', 30),
('user_mgmt.action.edit', '用户管理：编辑用户', 'user_mgmt', '用户管理', 10),
('role_mgmt.action.create', '角色管理：新建角色', 'role_mgmt', '角色管理', 10),
('role_mgmt.action.edit', '角色管理：编辑角色', 'role_mgmt', '角色管理', 20),
('role_mgmt.action.delete', '角色管理：删除角色', 'role_mgmt', '角色管理', 30),
('reconciliation.page.export', '对账：导出页', 'reconciliation', '对账', 10),
('reconciliation.action.download', '对账：下载文件', 'reconciliation', '对账', 20);

-- 将角色 JSON 菜单导入 role_allowed_nav（与 run_17_migrate_role_json_to_nav_cap.sql 一致）
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'inventory_query' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"inventory"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'inventory_ops' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"inventory"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'report_notes' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"report_export"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'report_records' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"report_export"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, jt.`v` FROM `role` r
JOIN JSON_TABLE(r.`allowed_menu_keys`, '$[*]' COLUMNS (`v` VARCHAR(64) PATH '$')) jt
WHERE r.`allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_menu_keys`) = 'ARRAY'
  AND jt.`v` NOT IN ('inventory', 'report_export');

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, jt.`v` FROM `role` r
JOIN JSON_TABLE(r.`allowed_capability_keys`, '$[*]' COLUMNS (`v` VARCHAR(128) PATH '$')) jt
WHERE r.`allowed_capability_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_capability_keys`) = 'ARRAY'
  AND JSON_LENGTH(r.`allowed_capability_keys`) > 0;
