-- BOM 表：父项版本（bom_header）与子项用量（bom_line）
-- 无外键约束：应用层保证关联列语义。

USE sydixon_order;
SET NAMES utf8mb4;

-- --------------------------------
-- BOM 主表：父项 + 版本 + 生效
-- --------------------------------
CREATE TABLE IF NOT EXISTS `bom_header` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `parent_kind` varchar(16) NOT NULL COMMENT 'finished / semi / material',
  `parent_product_id` int unsigned NOT NULL DEFAULT 0 COMMENT '当 parent_kind=finished 时使用',
  `parent_material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '当 parent_kind IN(semi,material) 时使用',
  `version_no` int unsigned NOT NULL COMMENT '版本号（递增）',
  `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '0=历史版本 1=当前生效',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_bom_header_parent_version` (`parent_kind`,`parent_product_id`,`parent_material_id`,`version_no`),
  KEY `idx_bom_header_parent` (`parent_kind`,`parent_product_id`,`parent_material_id`),
  KEY `idx_bom_header_active` (`parent_kind`,`parent_product_id`,`parent_material_id`,`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='BOM 主表：父项/版本';

-- --------------------------------
-- BOM 明细：子项 + 用量
-- --------------------------------
CREATE TABLE IF NOT EXISTS `bom_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `bom_header_id` int unsigned NOT NULL COMMENT '关联 bom_header.id（应用层保证）',
  `line_no` int unsigned NOT NULL COMMENT '行号（从 1 开始）',
  `child_kind` varchar(16) NOT NULL COMMENT 'semi / material',
  `child_material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '半成品/物料 id',
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL COMMENT '数量单位（用于展示）',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_bom_line_header_line` (`bom_header_id`,`line_no`),
  KEY `idx_bom_line_child` (`child_kind`,`child_material_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='BOM 明细：子项用量';

