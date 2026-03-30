-- 半成品/物料主数据表：用于库存 semi/material 入/出库的物料主数据匹配
-- 无外键约束：应用层保证关联列语义。

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `semi_material` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `kind` varchar(16) NOT NULL COMMENT 'semi / material',
  `code` varchar(64) NOT NULL COMMENT '半成品/物料编号',
  `name` varchar(128) NOT NULL COMMENT '名称',
  `spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `base_unit` varchar(16) DEFAULT NULL COMMENT '基础单位',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_semi_material_code` (`code`),
  KEY `idx_semi_material_kind` (`kind`),
  KEY `idx_semi_material_spec` (`spec`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='半成品/物料主数据';

