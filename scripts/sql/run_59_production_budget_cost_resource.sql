-- 生产预算成本：机台-操作员白名单、工序部门与能力工位映射、成本 scenario、物料标准单价
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

-- ----------------------------
-- 机台 ↔ 可操作员工（应用层逻辑关联）
-- ----------------------------
CREATE TABLE IF NOT EXISTS `machine_operator_allowlist` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `machine_id` int unsigned NOT NULL COMMENT 'machine.id',
  `employee_id` int unsigned NOT NULL COMMENT 'hr_employee.id',
  `capability_hr_department_id` int unsigned NOT NULL DEFAULT 0 COMMENT '能力表用工位；0=取该员工在能力表中的最优一条',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_machine_employee` (`machine_id`,`employee_id`),
  KEY `idx_moa_machine` (`machine_id`),
  KEY `idx_moa_employee` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台操作员白名单';

-- ----------------------------
-- 工序上的 hr_department_id → 能力表 hr_department_id 映射（多对多）
-- ----------------------------
CREATE TABLE IF NOT EXISTS `hr_department_capability_map` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT 'company.id',
  `process_hr_department_id` int unsigned NOT NULL COMMENT '路由/工序快照中的部门 id',
  `capability_hr_department_id` int unsigned NOT NULL COMMENT 'hr_employee_capability.hr_department_id',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dept_cap_map` (`company_id`,`process_hr_department_id`,`capability_hr_department_id`),
  KEY `idx_dept_cap_company_process` (`company_id`,`process_hr_department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工序部门与能力工位映射';

-- ----------------------------
-- production_cost_plan_detail：区分优化/指定两套分项
-- ----------------------------
SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'production_cost_plan_detail'
    AND COLUMN_NAME = 'scenario'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_cost_plan_detail`
    ADD COLUMN `scenario` varchar(16) NOT NULL DEFAULT ''optimized'' COMMENT ''optimized=最小期望成本 assigned=指定资源'' AFTER `preplan_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx := (
  SELECT COUNT(1)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'production_cost_plan_detail'
    AND INDEX_NAME = 'idx_cost_plan_preplan_scenario'
);
SET @sql := IF(
  @has_idx = 0,
  'ALTER TABLE `production_cost_plan_detail` ADD KEY `idx_cost_plan_preplan_scenario` (`preplan_id`,`scenario`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ----------------------------
-- production_work_order_operation：预算指定机台/操作员
-- ----------------------------
SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'production_work_order_operation'
    AND COLUMN_NAME = 'budget_machine_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_work_order_operation`
    ADD COLUMN `budget_machine_id` int unsigned NOT NULL DEFAULT 0 COMMENT ''预算指定 machine.id（machine_type 工序）'' AFTER `estimated_total_minutes`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'production_work_order_operation'
    AND COLUMN_NAME = 'budget_operator_employee_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_work_order_operation`
    ADD COLUMN `budget_operator_employee_id` int unsigned NOT NULL DEFAULT 0 COMMENT ''预算指定操作员 hr_employee.id'' AFTER `budget_machine_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ----------------------------
-- semi_material：标准单位成本（物料预算）
-- ----------------------------
SET @has_col := (
  SELECT COUNT(1)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'semi_material'
    AND COLUMN_NAME = 'standard_unit_cost'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `semi_material`
    ADD COLUMN `standard_unit_cost` decimal(18,4) DEFAULT NULL COMMENT ''标准单位成本（元/单位；预算用）'' AFTER `base_unit`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
