-- 库存进出批次表 + movement.movement_batch_id；能力 inventory_ops.movement_batch.void
USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `inventory_movement_batch` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL COMMENT 'finished / semi',
  `biz_date` date NOT NULL COMMENT '业务日期',
  `direction` varchar(8) NOT NULL COMMENT 'in=入库 out=出库',
  `source` varchar(16) NOT NULL COMMENT 'form=手工 excel=导入 delivery=送货出库',
  `line_count` int unsigned NOT NULL DEFAULT 0 COMMENT '明细行数',
  `original_filename` varchar(255) DEFAULT NULL COMMENT 'Excel 导入时的文件名',
  `source_delivery_id` int unsigned DEFAULT NULL COMMENT '送货批次时关联 delivery.id',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inv_mov_batch_delivery` (`source_delivery_id`),
  KEY `idx_inv_mov_batch_biz_date` (`biz_date`),
  KEY `idx_inv_mov_batch_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存进出批次（手工/导入/送货）';

ALTER TABLE `inventory_movement`
  ADD COLUMN `movement_batch_id` int unsigned DEFAULT NULL COMMENT '关联 inventory_movement_batch.id' AFTER `created_at`,
  ADD KEY `idx_inv_mov_batch` (`movement_batch_id`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('inventory_ops.movement_batch.void', '库存录入：撤销手工/导入批次', 'inventory_ops', '库存录入', 45)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`), `nav_item_code`=VALUES(`nav_item_code`), `group_label`=VALUES(`group_label`), `sort_order`=VALUES(`sort_order`);

UPDATE `sys_capability`
SET `title`='库存录入：库存批次列表'
WHERE `code`='inventory_ops.movement.list';

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT `role_id`, 'inventory_ops.movement_batch.void'
FROM `role_allowed_capability`
WHERE `cap_code` = 'inventory_ops.movement.delete';
