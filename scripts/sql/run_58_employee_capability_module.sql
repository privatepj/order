-- P4: 人员能力表（按员工 + 工位）+ 工资(月薪/时薪) 扩展
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

-- ----------------------------
-- 扩展 hr_payroll_line：monthly/hourly 工资口径所需字段
-- ----------------------------

SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'hr_payroll_line'
    AND COLUMN_NAME = 'wage_kind'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `hr_payroll_line`
    ADD COLUMN `wage_kind` varchar(16) NOT NULL DEFAULT ''monthly'' COMMENT ''月薪/时薪：monthly/hourly'' AFTER `period`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'hr_payroll_line'
    AND COLUMN_NAME = 'work_hours'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `hr_payroll_line`
    ADD COLUMN `work_hours` decimal(12,2) DEFAULT NULL COMMENT ''换算时薪/产能成本所用工时（小时；月薪口径可填）'' AFTER `wage_kind`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'hr_payroll_line'
    AND COLUMN_NAME = 'hourly_rate'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `hr_payroll_line`
    ADD COLUMN `hourly_rate` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT ''时薪（元/小时；小时口径使用）'' AFTER `work_hours`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ----------------------------
-- 新增 hr_employee_capability：能力表累计统计
-- ----------------------------

CREATE TABLE IF NOT EXISTS `hr_employee_capability` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `employee_id` int unsigned NOT NULL COMMENT 'hr_employee.id',
  `hr_department_id` int unsigned NOT NULL COMMENT 'hr_department.id（工种/工位维度）',

  `good_qty_total` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT '累计良品数量',
  `bad_qty_total` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT '累计不良数量',
  `produced_qty_total` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT '累计总产出（good+bad）',
  `work_order_cnt_total` int unsigned NOT NULL DEFAULT 0 COMMENT '累计干过的工单数（基于 work_order_id distinct 统计）',
  `worked_minutes_total` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT '累计工时（分钟；用于小时产能/成本）',
  `labor_cost_total` decimal(18,2) NOT NULL DEFAULT 0.00 COMMENT '累计劳动力成本（用于单件成本）',

  `processed_to` datetime DEFAULT NULL COMMENT '能力表累计进度：已覆盖到的截止时间（用于按小时增量计算）',

  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hec_company_emp_dept` (`company_id`,`employee_id`,`hr_department_id`),
  KEY `idx_hec_employee` (`employee_id`,`hr_department_id`),
  KEY `idx_hec_processed_to` (`processed_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人员能力表（累计统计）';

-- ----------------------------
-- RBAC：菜单 + 能力键 + warehouse 可访问
-- ----------------------------

SET @nav_hr_employee_capability := (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_hr' LIMIT 1);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_hr_employee_capability, 'hr_employee_capability', '人员能力表', 'main.hr_employee_capability_list', 56, 1, 0, 1, 96)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('hr_employee_capability.view', '人员能力表：查看', 'hr_employee_capability', '人力资源', 660)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_employee_capability' FROM `role` r WHERE r.`code`='warehouse';

