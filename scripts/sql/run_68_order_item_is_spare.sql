USE sydixon_order;
SET NAMES utf8mb4;

SET @is_spare_exists := (
  SELECT COUNT(1)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'order_item'
    AND COLUMN_NAME = 'is_spare'
);

SET @ddl := IF(
  @is_spare_exists = 0,
  'ALTER TABLE `order_item` ADD COLUMN `is_spare` TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''是否备品'' AFTER `is_sample`',
  'SELECT ''column `order_item.is_spare` already exists'' AS msg'
);

PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
