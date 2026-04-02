-- 机台成本字段 + 机台排产 dispatch log
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

-- machine：购入价格/累计生产/累计运行/单次运行成本

SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'machine'
    AND COLUMN_NAME = 'machine_cost_purchase_price'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine` ADD COLUMN `machine_cost_purchase_price` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT ''购入价格（管理员维护）''',
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
    AND COLUMN_NAME = 'machine_accum_produced_qty'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine` ADD COLUMN `machine_accum_produced_qty` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT ''机台累计生产个数''',
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
    AND COLUMN_NAME = 'machine_accum_runtime_hours'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine` ADD COLUMN `machine_accum_runtime_hours` decimal(14,4) NOT NULL DEFAULT 0.0000 COMMENT ''机台累计运行时长（小时）''',
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
    AND COLUMN_NAME = 'machine_single_run_cost'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine` ADD COLUMN `machine_single_run_cost` decimal(14,2) DEFAULT NULL COMMENT ''机台单次运行成本（管理员维护）''',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- dispatch log 表
CREATE TABLE IF NOT EXISTS `machine_schedule_dispatch_log` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `machine_id` int unsigned NOT NULL COMMENT '机台 machine.id',
  `booking_id` int unsigned NOT NULL COMMENT '机台排班时间窗 machine_schedule_booking.id',
  `dispatch_start_at` datetime DEFAULT NULL COMMENT '排产开始（冗余）',
  `dispatch_end_at` datetime DEFAULT NULL COMMENT '排产结束（冗余）',
  `planned_runtime_hours` decimal(14,4) NOT NULL DEFAULT 0.0000 COMMENT '计划运行时长（小时）',
  `state` varchar(16) NOT NULL DEFAULT 'scheduled' COMMENT 'scheduled/reported',
  `actual_produced_qty` decimal(18,4) DEFAULT NULL COMMENT '实际产量（个）',
  `actual_runtime_hours` decimal(14,4) DEFAULT NULL COMMENT '实际运行时长（小时）',
  `work_order_id` int unsigned DEFAULT NULL COMMENT '报工对应 work_order.id',
  `reported_by` int unsigned DEFAULT NULL COMMENT '报工人 user.id',
  `reported_at` datetime DEFAULT NULL COMMENT '报工时间',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ms_dispatch_booking` (`booking_id`),
  KEY `idx_ms_dispatch_machine_start` (`machine_id`,`dispatch_start_at`),
  KEY `idx_ms_dispatch_state` (`state`),
  KEY `idx_ms_dispatch_work_order` (`work_order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台排产记录（booking -> dispatch log）';

