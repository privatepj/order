-- 机台台账：行政部门归属（与 default_capability_* 能力工位语义区分；无 FOREIGN KEY）
USE sydixon_order;
SET NAMES utf8mb4;

SET @col_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'machine'
    AND COLUMN_NAME = 'owning_hr_department_id'
);

SET @sql := IF(
  @col_exists = 0,
  'ALTER TABLE `machine`
     ADD COLUMN `owning_hr_department_id` int unsigned NOT NULL DEFAULT 0
       COMMENT ''归属行政部门 hr_department.id；0=未分配''
       AFTER `default_capability_work_type_id`,
     ADD KEY `idx_machine_owning_dept` (`owning_hr_department_id`)',
  'SELECT ''column machine.owning_hr_department_id already exists'' AS msg'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
