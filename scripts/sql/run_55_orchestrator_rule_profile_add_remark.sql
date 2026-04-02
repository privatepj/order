-- P4 hotfix: align orchestrator_rule_profile with ORM
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'orchestrator_rule_profile'
    AND COLUMN_NAME = 'remark'
);

SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `orchestrator_rule_profile` ADD COLUMN `remark` varchar(255) DEFAULT NULL AFTER `is_active`',
  'SELECT 1'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
