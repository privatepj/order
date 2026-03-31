-- 采购管理模块：表 + 导航 + 能力 + 角色菜单
-- 无外键约束；应用层保证关联语义

USE sydixon_order;
SET NAMES utf8mb4;

DROP TABLE IF EXISTS `purchase_stock_in`;
DROP TABLE IF EXISTS `purchase_receipt`;
DROP TABLE IF EXISTS `purchase_order`;
DROP TABLE IF EXISTS `purchase_requisition`;

CREATE TABLE `purchase_requisition` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `req_no` varchar(32) NOT NULL COMMENT '请购单号',
  `requester_user_id` int unsigned NOT NULL COMMENT '申请人 user.id',
  `supplier_name` varchar(128) NOT NULL COMMENT '供应商',
  `item_name` varchar(128) NOT NULL COMMENT '物料名称',
  `item_spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `qty` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '请购数量',
  `unit` varchar(16) NOT NULL DEFAULT 'pcs' COMMENT '单位',
  `expected_date` date DEFAULT NULL COMMENT '期望到货日期',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/ordered/cancelled',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_requisition_no` (`req_no`),
  KEY `idx_purchase_requisition_company` (`company_id`),
  KEY `idx_purchase_requisition_requester` (`requester_user_id`),
  KEY `idx_purchase_requisition_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购请购单';

CREATE TABLE `purchase_order` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `po_no` varchar(32) NOT NULL COMMENT '采购单号',
  `requisition_id` int unsigned DEFAULT NULL COMMENT '请购单 purchase_requisition.id',
  `buyer_user_id` int unsigned NOT NULL COMMENT '采购员 user.id',
  `supplier_name` varchar(128) NOT NULL COMMENT '供应商',
  `item_name` varchar(128) NOT NULL COMMENT '物料名称',
  `item_spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `qty` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '采购数量',
  `unit` varchar(16) NOT NULL DEFAULT 'pcs' COMMENT '单位',
  `unit_price` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '单价',
  `amount` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '金额',
  `expected_date` date DEFAULT NULL COMMENT '期望到货日期',
  `status` varchar(24) NOT NULL DEFAULT 'draft' COMMENT 'draft/ordered/partially_received/received/cancelled',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_order_no` (`po_no`),
  KEY `idx_purchase_order_company` (`company_id`),
  KEY `idx_purchase_order_req` (`requisition_id`),
  KEY `idx_purchase_order_buyer` (`buyer_user_id`),
  KEY `idx_purchase_order_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购单';

CREATE TABLE `purchase_receipt` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `receipt_no` varchar(32) NOT NULL COMMENT '收货单号',
  `purchase_order_id` int unsigned NOT NULL COMMENT '采购单 purchase_order.id',
  `receiver_user_id` int unsigned NOT NULL COMMENT '收货人 user.id',
  `received_qty` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '收货数量',
  `received_at` datetime NOT NULL COMMENT '收货时间',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/posted',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_receipt_no` (`receipt_no`),
  KEY `idx_purchase_receipt_company` (`company_id`),
  KEY `idx_purchase_receipt_po` (`purchase_order_id`),
  KEY `idx_purchase_receipt_receiver` (`receiver_user_id`),
  KEY `idx_purchase_receipt_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购收货单';

CREATE TABLE `purchase_stock_in` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `stock_in_no` varchar(32) NOT NULL COMMENT '入库单号',
  `receipt_id` int unsigned NOT NULL COMMENT '收货单 purchase_receipt.id',
  `qty` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '入库数量',
  `storage_area` varchar(64) DEFAULT NULL COMMENT '仓储区',
  `stock_in_at` datetime NOT NULL COMMENT '入库时间',
  `created_by` int unsigned NOT NULL COMMENT '创建人 user.id',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_stock_in_no` (`stock_in_no`),
  KEY `idx_purchase_stock_in_company` (`company_id`),
  KEY `idx_purchase_stock_in_receipt` (`receipt_id`),
  KEY `idx_purchase_stock_in_creator` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购入库记录';

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (NULL, 'nav_procurement', '采购管理', NULL, 18, 1, 0, 0, NULL)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

SET @nav_procurement_id = (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_procurement' LIMIT 1);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_procurement_id, 'procurement_requisition', '采购请购', 'main.procurement_requisition_list', 10, 1, 0, 1, 102),
  (@nav_procurement_id, 'procurement_order', '采购单', 'main.procurement_order_list', 20, 1, 0, 1, 103),
  (@nav_procurement_id, 'procurement_receipt', '采购收货', 'main.procurement_receipt_list', 30, 1, 0, 1, 104),
  (@nav_procurement_id, 'procurement_stockin', '采购入库', 'main.procurement_stockin_list', 40, 1, 0, 1, 105)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('procurement_requisition.filter.keyword', '采购请购：关键词', 'procurement_requisition', '采购管理', 900),
('procurement_requisition.action.create', '采购请购：新建', 'procurement_requisition', '采购管理', 910),
('procurement_requisition.action.edit', '采购请购：编辑', 'procurement_requisition', '采购管理', 920),
('procurement_requisition.action.delete', '采购请购：删除', 'procurement_requisition', '采购管理', 930),
('procurement_order.filter.keyword', '采购单：关键词', 'procurement_order', '采购管理', 940),
('procurement_order.action.create', '采购单：新建', 'procurement_order', '采购管理', 950),
('procurement_order.action.edit', '采购单：编辑', 'procurement_order', '采购管理', 960),
('procurement_order.action.delete', '采购单：删除', 'procurement_order', '采购管理', 970),
('procurement_order.action.detail', '采购单：详情', 'procurement_order', '采购管理', 980),
('procurement_receipt.filter.keyword', '采购收货：关键词', 'procurement_receipt', '采购管理', 990),
('procurement_receipt.action.create', '采购收货：新建', 'procurement_receipt', '采购管理', 1000),
('procurement_receipt.action.edit', '采购收货：编辑', 'procurement_receipt', '采购管理', 1010),
('procurement_receipt.action.delete', '采购收货：删除', 'procurement_receipt', '采购管理', 1020),
('procurement_stockin.filter.keyword', '采购入库：关键词', 'procurement_stockin', '采购管理', 1030)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_requisition' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_order' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_receipt' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_stockin' FROM `role` r WHERE r.`code`='warehouse';
