-- 生产管理表：预生产计划 / 工作单 / 缺料明细
-- 无外键约束：应用层保证 join 语义。

USE sydixon_order;
SET NAMES utf8mb4;

-- --------------------------------
-- 预生产计划头
-- --------------------------------
CREATE TABLE IF NOT EXISTS `production_preplan` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `source_type` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual=手工预计划 order_shortage=由订单缺货生成 combined=合并测算',
  `plan_date` date NOT NULL COMMENT '预生产计划日期',
  `customer_id` int unsigned NOT NULL DEFAULT 0 COMMENT '关联 customer.id（可为空用 0 占位）',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/planned/closed',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_preplan_customer` (`customer_id`),
  KEY `idx_preplan_plan_date` (`plan_date`),
  KEY `idx_preplan_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预生产计划';

-- --------------------------------
-- 预生产计划明细（根需求）
-- --------------------------------
CREATE TABLE IF NOT EXISTS `production_preplan_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `line_no` int unsigned NOT NULL DEFAULT 1 COMMENT '行号（从 1 开始）',
  `source_type` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual=手工预计划 order_item=订单缺货生成',
  `source_order_item_id` int unsigned DEFAULT NULL,
  `product_id` int unsigned NOT NULL DEFAULT 0 COMMENT '成品 product.id',
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_preplan_line` (`preplan_id`,`line_no`),
  KEY `idx_preplan_line_preplan` (`preplan_id`),
  KEY `idx_preplan_line_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预生产计划明细（根需求）';

-- --------------------------------
-- 生产工作单（父项 netted 后的净需求）
-- --------------------------------
CREATE TABLE IF NOT EXISTS `production_work_order` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `root_preplan_line_id` int unsigned DEFAULT NULL COMMENT '追溯到根需求行（订单缺货行/预计划行）',
  `parent_kind` varchar(16) NOT NULL COMMENT 'finished=成品 semi=半成品 material=物料',
  `parent_product_id` int unsigned NOT NULL DEFAULT 0 COMMENT 'parent_kind=finished 时使用',
  `parent_material_id` int unsigned NOT NULL DEFAULT 0 COMMENT 'parent_kind IN(semi,material) 时使用',
  `plan_date` date NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'planned' COMMENT 'planned/released/closed/cancelled',
  `demand_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '根需求推导出的总需求',
  `stock_covered_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '库存覆盖数量（计算时点）',
  `to_produce_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '需要生产的净数量',
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `remark` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_work_order_preplan` (`preplan_id`),
  KEY `idx_work_order_root_line` (`root_preplan_line_id`),
  KEY `idx_work_order_parent` (`parent_kind`,`parent_product_id`,`parent_material_id`),
  KEY `idx_work_order_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生产工作单';

-- --------------------------------
-- 工作单需求/缺料明细（BOM 子项）
-- --------------------------------
CREATE TABLE IF NOT EXISTS `production_component_need` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `work_order_id` int unsigned NOT NULL,
  `root_preplan_line_id` int unsigned DEFAULT NULL COMMENT '追溯到根需求行',
  `bom_header_id` int unsigned DEFAULT NULL COMMENT '关联 bom_header.id（用于追溯）',
  `bom_line_id` int unsigned DEFAULT NULL COMMENT '关联 bom_line.id（用于追溯）',
  `child_kind` varchar(16) NOT NULL COMMENT 'semi/material',
  `child_material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '半成品/物料 id',
  `required_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `stock_covered_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `shortage_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `coverage_mode` varchar(16) NOT NULL DEFAULT 'stock' COMMENT 'stock=库存覆盖',
  `storage_area_hint` varchar(32) DEFAULT NULL COMMENT '未来：精确到仓储区的出入库提示',
  `unit` varchar(16) DEFAULT NULL COMMENT '用于展示',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_component_need_wo_bom_line` (`work_order_id`,`bom_line_id`),
  KEY `idx_component_need_preplan` (`preplan_id`),
  KEY `idx_component_need_wo` (`work_order_id`),
  KEY `idx_component_need_child` (`child_kind`,`child_material_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作单需求/缺料明细';

