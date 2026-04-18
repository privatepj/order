-- 库存批次头 source：放宽为自定义手工说明（系统值仍为 form/excel/delivery）
ALTER TABLE `inventory_movement_batch`
  MODIFY COLUMN `source` varchar(64) NOT NULL COMMENT 'form/excel/delivery 为系统值，其余为手工填写的来源说明';
