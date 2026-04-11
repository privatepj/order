USE sydixon_order;
SET NAMES utf8mb4;

SET @db := DATABASE();

SET @confirmed_exists := (
  SELECT COUNT(1)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db
    AND TABLE_NAME = 'production_work_order_operation_plan'
    AND COLUMN_NAME = 'confirmed_at'
);

SET @ddl := IF(
  @confirmed_exists = 0,
  'ALTER TABLE `production_work_order_operation_plan`
     ADD COLUMN `confirmed_at` datetime DEFAULT NULL COMMENT ''确认计划时间'' AFTER `remark`,
     ADD COLUMN `confirmed_by` int unsigned DEFAULT NULL COMMENT ''确认人 user.id'' AFTER `confirmed_at`,
     ADD COLUMN `committed_machine_booking_id` int unsigned NOT NULL DEFAULT 0 COMMENT ''机台排班 booking'' AFTER `confirmed_by`,
     ADD COLUMN `committed_employee_booking_id` int unsigned NOT NULL DEFAULT 0 COMMENT ''人员排班 booking'' AFTER `committed_machine_booking_id`',
  'SELECT ''column production_work_order_operation_plan.confirmed_at already exists'' AS msg'
);

PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS `production_schedule_commit_row` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `operation_id` int unsigned NOT NULL COMMENT 'production_work_order_operation.id',
  `machine_dispatch_log_id` int unsigned NOT NULL DEFAULT 0,
  `dispatch_booking_id` int unsigned NOT NULL DEFAULT 0 COMMENT '挂 dispatch 的 machine_schedule_booking.id',
  `restore_parent_booking_id` int unsigned NOT NULL DEFAULT 0 COMMENT '被缩短的父 booking',
  `restore_parent_end_at` datetime DEFAULT NULL COMMENT '父 booking 切分前的 end_at',
  `delete_middle_booking_id` int unsigned NOT NULL DEFAULT 0 COMMENT '独立中段 booking',
  `delete_tail_booking_id` int unsigned NOT NULL DEFAULT 0 COMMENT '尾段 booking',
  `employee_booking_id` int unsigned NOT NULL DEFAULT 0 COMMENT '人员占用段（多为 unavailable 中段）',
  `emp_restore_parent_booking_id` int unsigned NOT NULL DEFAULT 0,
  `emp_restore_parent_end_at` datetime DEFAULT NULL,
  `emp_delete_middle_booking_id` int unsigned NOT NULL DEFAULT 0,
  `emp_delete_tail_booking_id` int unsigned NOT NULL DEFAULT 0,
  `emp_booking_mode` varchar(16) NOT NULL DEFAULT 'split' COMMENT 'split=切分; mask_parent=整窗改为 unavailable',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_pscr_operation` (`operation_id`),
  KEY `idx_pscr_preplan` (`preplan_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预计划确认排产与机台切分痕迹';
