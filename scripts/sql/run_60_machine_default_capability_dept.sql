-- 机种/机台：默认「能力工位」hr_department.id（白名单能力工位填 0 时用于解析工种）
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'machine_type'
    AND COLUMN_NAME = 'default_capability_hr_department_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine_type`
    ADD COLUMN `default_capability_hr_department_id` int unsigned NOT NULL DEFAULT 0 COMMENT ''该机种操作默认对应的能力工位(hr_department.id)；0=未配置'' AFTER `remark`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'machine'
    AND COLUMN_NAME = 'default_capability_hr_department_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine`
    ADD COLUMN `default_capability_hr_department_id` int unsigned NOT NULL DEFAULT 0 COMMENT ''覆盖机种默认；0=沿用机种'' AFTER `remark`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
