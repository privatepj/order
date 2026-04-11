USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `supplier` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `name` varchar(128) NOT NULL,
  `contact_name` varchar(64) DEFAULT NULL,
  `phone` varchar(32) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_supplier_company_name` (`company_id`, `name`),
  KEY `idx_supplier_company_active` (`company_id`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商主数据';

CREATE TABLE IF NOT EXISTS `supplier_material_map` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `supplier_id` int unsigned NOT NULL,
  `material_id` int unsigned NOT NULL,
  `is_preferred` tinyint(1) NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `last_unit_price` decimal(14,2) DEFAULT NULL,
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_supplier_material` (`supplier_id`, `material_id`),
  KEY `idx_supplier_material_company` (`company_id`),
  KEY `idx_supplier_material_supplier_active` (`supplier_id`, `is_active`),
  KEY `idx_supplier_material_material_active` (`material_id`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商-物料关系';

CREATE TABLE IF NOT EXISTS `purchase_requisition_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `requisition_id` int unsigned NOT NULL,
  `line_no` int unsigned NOT NULL DEFAULT 1,
  `supplier_id` int unsigned DEFAULT NULL,
  `material_id` int unsigned DEFAULT NULL,
  `supplier_name` varchar(128) NOT NULL,
  `item_name` varchar(128) NOT NULL,
  `item_spec` varchar(128) DEFAULT NULL,
  `qty` decimal(14,2) NOT NULL DEFAULT 0.00,
  `unit` varchar(16) NOT NULL DEFAULT 'pcs',
  `expected_date` date DEFAULT NULL,
  `status` varchar(24) NOT NULL DEFAULT 'pending_order',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_requisition_line` (`requisition_id`, `line_no`),
  KEY `idx_purchase_requisition_line_company` (`company_id`),
  KEY `idx_purchase_requisition_line_supplier` (`supplier_id`),
  KEY `idx_purchase_requisition_line_material` (`material_id`),
  KEY `idx_purchase_requisition_line_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购请购明细';

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_requisition' AND COLUMN_NAME = 'printed_at'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_requisition` ADD COLUMN `printed_at` datetime DEFAULT NULL AFTER `status`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_requisition' AND COLUMN_NAME = 'signed_at'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_requisition` ADD COLUMN `signed_at` datetime DEFAULT NULL AFTER `printed_at`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_requisition' AND COLUMN_NAME = 'signed_by'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_requisition` ADD COLUMN `signed_by` int unsigned DEFAULT NULL AFTER `signed_at`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx := (
  SELECT COUNT(1) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_requisition' AND INDEX_NAME = 'idx_purchase_requisition_signed_by'
);
SET @sql := IF(
  @has_idx = 0,
  'ALTER TABLE `purchase_requisition` ADD KEY `idx_purchase_requisition_signed_by` (`signed_by`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'requisition_line_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `requisition_line_id` int unsigned DEFAULT NULL AFTER `requisition_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'supplier_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `supplier_id` int unsigned DEFAULT NULL AFTER `buyer_user_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'material_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `material_id` int unsigned DEFAULT NULL AFTER `supplier_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'supplier_contact_name'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `supplier_contact_name` varchar(64) DEFAULT NULL AFTER `supplier_name`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'supplier_phone'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `supplier_phone` varchar(32) DEFAULT NULL AFTER `supplier_contact_name`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'supplier_address'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `supplier_address` varchar(255) DEFAULT NULL AFTER `supplier_phone`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'ordered_at'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `ordered_at` datetime DEFAULT NULL AFTER `status`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'ordered_by'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `ordered_by` int unsigned DEFAULT NULL AFTER `ordered_at`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'printed_at'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `printed_at` datetime DEFAULT NULL AFTER `ordered_by`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND COLUMN_NAME = 'reconcile_status'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_order` ADD COLUMN `reconcile_status` varchar(24) NOT NULL DEFAULT ''pending'' AFTER `printed_at`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_purchase_order_requisition_line';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `purchase_order` ADD KEY `idx_purchase_order_requisition_line` (`requisition_line_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_purchase_order_supplier_id';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `purchase_order` ADD KEY `idx_purchase_order_supplier_id` (`supplier_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_purchase_order_material_id';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `purchase_order` ADD KEY `idx_purchase_order_material_id` (`material_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_purchase_order_ordered_by';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_order' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `purchase_order` ADD KEY `idx_purchase_order_ordered_by` (`ordered_by`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_receipt' AND COLUMN_NAME = 'reconcile_status'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_receipt` ADD COLUMN `reconcile_status` varchar(24) NOT NULL DEFAULT ''pending'' AFTER `status`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_receipt' AND COLUMN_NAME = 'reconcile_note'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_receipt` ADD COLUMN `reconcile_note` varchar(500) DEFAULT NULL AFTER `reconcile_status`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_receipt' AND COLUMN_NAME = 'reconciled_at'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_receipt` ADD COLUMN `reconciled_at` datetime DEFAULT NULL AFTER `reconcile_note`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_receipt' AND COLUMN_NAME = 'reconciled_by'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_receipt` ADD COLUMN `reconciled_by` int unsigned DEFAULT NULL AFTER `reconciled_at`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_purchase_receipt_reconciled_by';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_receipt' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `purchase_receipt` ADD KEY `idx_purchase_receipt_reconciled_by` (`reconciled_by`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND COLUMN_NAME = 'purchase_order_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_stock_in` ADD COLUMN `purchase_order_id` int unsigned DEFAULT NULL AFTER `receipt_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND COLUMN_NAME = 'received_qty'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_stock_in` ADD COLUMN `received_qty` decimal(14,2) NOT NULL DEFAULT 0.00 AFTER `qty`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND COLUMN_NAME = 'warehouse_qty'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_stock_in` ADD COLUMN `warehouse_qty` decimal(14,2) NOT NULL DEFAULT 0.00 AFTER `received_qty`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND COLUMN_NAME = 'variance_qty'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_stock_in` ADD COLUMN `variance_qty` decimal(14,2) NOT NULL DEFAULT 0.00 AFTER `warehouse_qty`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND COLUMN_NAME = 'approval_status'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_stock_in` ADD COLUMN `approval_status` varchar(24) NOT NULL DEFAULT ''matched'' AFTER `variance_qty`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND COLUMN_NAME = 'approved_by'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_stock_in` ADD COLUMN `approved_by` int unsigned DEFAULT NULL AFTER `created_by`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND COLUMN_NAME = 'approved_at'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `purchase_stock_in` ADD COLUMN `approved_at` datetime DEFAULT NULL AFTER `approved_by`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_purchase_stock_in_po';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `purchase_stock_in` ADD KEY `idx_purchase_stock_in_po` (`purchase_order_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_purchase_stock_in_approved_by';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'purchase_stock_in' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `purchase_stock_in` ADD KEY `idx_purchase_stock_in_approved_by` (`approved_by`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_movement' AND COLUMN_NAME = 'source_purchase_order_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `inventory_movement` ADD COLUMN `source_purchase_order_id` int unsigned DEFAULT NULL AFTER `source_delivery_item_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_movement' AND COLUMN_NAME = 'source_purchase_receipt_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `inventory_movement` ADD COLUMN `source_purchase_receipt_id` int unsigned DEFAULT NULL AFTER `source_purchase_order_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_inv_mov_purchase_order';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_movement' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `inventory_movement` ADD KEY `idx_inv_mov_purchase_order` (`source_purchase_order_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_name := 'idx_inv_mov_purchase_receipt';
SET @sql := IF(
  (SELECT COUNT(1) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'inventory_movement' AND INDEX_NAME = @idx_name) = 0,
  'ALTER TABLE `inventory_movement` ADD KEY `idx_inv_mov_purchase_receipt` (`source_purchase_receipt_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @nav_procurement_id = (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_procurement' LIMIT 1);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_procurement_id, 'procurement_supplier', '供应商', 'main.procurement_supplier_list', 5, 1, 0, 1, 101)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('procurement_supplier.filter.keyword', '供应商：关键词', 'procurement_supplier', '采购管理', 880),
('procurement_supplier.action.create', '供应商：新建', 'procurement_supplier', '采购管理', 881),
('procurement_supplier.action.edit', '供应商：编辑', 'procurement_supplier', '采购管理', 882),
('procurement_supplier.action.delete', '供应商：删除', 'procurement_supplier', '采购管理', 883),
('procurement_requisition.action.print', '采购请购：打印', 'procurement_requisition', '采购管理', 931),
('procurement_requisition.action.mark_signed', '采购请购：标记已签字', 'procurement_requisition', '采购管理', 932),
('procurement_requisition.action.generate_orders', '采购请购：生成采购单', 'procurement_requisition', '采购管理', 933),
('procurement_order.action.print', '采购单：打印', 'procurement_order', '采购管理', 981),
('procurement_order.action.mark_ordered', '采购单：标记已下单', 'procurement_order', '采购管理', 982),
('procurement_receipt.action.compare', '采购收货：查看对比', 'procurement_receipt', '采购管理', 1021),
('procurement_receipt.action.approve_stockin', '采购收货：确认采购入库', 'procurement_receipt', '采购管理', 1022)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_supplier' FROM `role` r WHERE r.`code`='warehouse';
