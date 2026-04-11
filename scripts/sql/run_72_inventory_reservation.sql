-- 生产预计划「库存占用」：预留明细（不写入 inventory_movement；无 DB 外键）
CREATE TABLE IF NOT EXISTS `inventory_reservation` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL COMMENT 'finished / semi / material',
  `product_id` int unsigned NOT NULL DEFAULT 0 COMMENT '成品时 product.id',
  `material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '半成品/物料时 semi_material.id',
  `storage_area` varchar(32) NOT NULL DEFAULT '' COMMENT '与台账一致；当前测算按全仓汇总预留',
  `ref_type` varchar(16) NOT NULL COMMENT 'preplan 等',
  `ref_id` int unsigned NOT NULL COMMENT '如 production_preplan.id',
  `reserved_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `status` varchar(16) NOT NULL DEFAULT 'active' COMMENT 'active=占用中 released=已释放 consumed=已转实出',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_inv_res_cat_item` (`category`,`product_id`,`material_id`),
  KEY `idx_inv_res_ref` (`ref_type`,`ref_id`),
  KEY `idx_inv_res_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存预留（计划占用，非出库流水）';
