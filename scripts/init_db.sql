-- 工厂订单系统 - MySQL 初始化脚本
-- 使用前请先创建数据库: CREATE DATABASE IF NOT EXISTS sydixon_order DEFAULT CHARSET utf8mb4;

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
  `express_company_id` int unsigned NOT NULL COMMENT '快递公司',
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

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- 初始数据：角色
-- ----------------------------
INSERT INTO `role` (`name`, `code`, `description`, `allowed_menu_keys`) VALUES
('管理员', 'admin', '系统管理员', NULL),
('销售', 'sales', '销售员', CAST('["order","delivery","customer","product","customer_product","reconciliation"]' AS JSON)),
('仓管', 'warehouse', '仓管员', CAST('["order","delivery","express","customer","product","customer_product","reconciliation"]' AS JSON)),
('财务', 'finance', '财务人员', CAST('["order","delivery","customer","product","customer_product","reconciliation"]' AS JSON)),
('待分配', 'pending', '注册后等待管理员分配', CAST('[]' AS JSON));

-- ----------------------------
-- 初始数据：管理员用户 (默认密码 password，请首次登录后修改)
-- 按当前配置，密码以明文方式存储
-- ----------------------------
INSERT INTO `user` (`username`, `password_hash`, `name`, `role_id`, `is_active`) VALUES
('admin', 'password', '管理员', 1, 1);
