USE sydixon_order;
SET NAMES utf8mb4;

-- HR 工种解耦重构
-- 目标：
-- 1. 部门仅表示组织归属
-- 2. 工种表示生产技能/能力/计件/人工资源维度
-- 3. 人员归属一个部门，可绑定一个主工种和多个辅工种
-- 约束：不创建数据库外键，仅补充表、字段、索引与兼容回填

CREATE TABLE IF NOT EXISTS `hr_work_type` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `name` varchar(128) NOT NULL,
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_name` (`company_id`, `name`),
  KEY `idx_company_active_sort` (`company_id`, `is_active`, `sort_order`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工种主数据';

CREATE TABLE IF NOT EXISTS `hr_employee_work_type` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `employee_id` int unsigned NOT NULL,
  `work_type_id` int unsigned NOT NULL,
  `is_primary` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_employee_work_type` (`employee_id`, `work_type_id`),
  KEY `idx_employee_primary` (`employee_id`, `is_primary`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='员工-工种关系';

CREATE TABLE IF NOT EXISTS `hr_department_work_type_map` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `department_id` int unsigned NOT NULL,
  `work_type_id` int unsigned NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_dept_work_type` (`company_id`, `department_id`, `work_type_id`),
  KEY `idx_company_dept_active` (`company_id`, `department_id`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门-工种允许关系';

CREATE TABLE IF NOT EXISTS `hr_work_type_piece_rate` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `work_type_id` int unsigned NOT NULL,
  `period` varchar(7) NOT NULL COMMENT 'YYYY-MM',
  `rate_per_unit` decimal(14,4) NOT NULL DEFAULT 0.0000 COMMENT '元/件',
  `remark` varchar(500) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_work_type_period` (`company_id`, `work_type_id`, `period`),
  KEY `idx_company_period` (`company_id`, `period`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工种计件单价';

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hr_employee' AND COLUMN_NAME = 'main_work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `hr_employee` ADD COLUMN `main_work_type_id` int unsigned DEFAULT NULL AFTER `job_title`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx := (
  SELECT COUNT(1) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hr_employee' AND INDEX_NAME = 'idx_main_work_type_id'
);
SET @sql := IF(
  @has_idx = 0,
  'ALTER TABLE `hr_employee` ADD KEY `idx_main_work_type_id` (`main_work_type_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hr_employee_capability' AND COLUMN_NAME = 'work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `hr_employee_capability` ADD COLUMN `work_type_id` int unsigned DEFAULT NULL AFTER `hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hr_employee_schedule_booking' AND COLUMN_NAME = 'work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `hr_employee_schedule_booking` ADD COLUMN `work_type_id` int unsigned DEFAULT NULL AFTER `hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'machine_type' AND COLUMN_NAME = 'default_capability_work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine_type` ADD COLUMN `default_capability_work_type_id` int unsigned NOT NULL DEFAULT 0 AFTER `default_capability_hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'machine' AND COLUMN_NAME = 'default_capability_work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine` ADD COLUMN `default_capability_work_type_id` int unsigned NOT NULL DEFAULT 0 AFTER `default_capability_hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'machine_operator_allowlist' AND COLUMN_NAME = 'capability_work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `machine_operator_allowlist` ADD COLUMN `capability_work_type_id` int unsigned NOT NULL DEFAULT 0 AFTER `capability_hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'production_process_template_step' AND COLUMN_NAME = 'hr_work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_process_template_step` ADD COLUMN `hr_work_type_id` int unsigned NOT NULL DEFAULT 0 AFTER `hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'production_product_routing_step' AND COLUMN_NAME = 'hr_work_type_id_override'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_product_routing_step` ADD COLUMN `hr_work_type_id_override` int unsigned NOT NULL DEFAULT 0 AFTER `hr_department_id_override`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'production_process_node' AND COLUMN_NAME = 'hr_work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_process_node` ADD COLUMN `hr_work_type_id` int unsigned NOT NULL DEFAULT 0 AFTER `hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'production_routing_node_override' AND COLUMN_NAME = 'hr_work_type_id_override'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_routing_node_override` ADD COLUMN `hr_work_type_id_override` int unsigned NOT NULL DEFAULT 0 AFTER `hr_department_id_override`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'production_work_order_operation' AND COLUMN_NAME = 'hr_work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_work_order_operation` ADD COLUMN `hr_work_type_id` int unsigned NOT NULL DEFAULT 0 AFTER `hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_col := (
  SELECT COUNT(1) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'production_work_order_operation_plan' AND COLUMN_NAME = 'hr_work_type_id'
);
SET @sql := IF(
  @has_col = 0,
  'ALTER TABLE `production_work_order_operation_plan` ADD COLUMN `hr_work_type_id` int unsigned NOT NULL DEFAULT 0 AFTER `hr_department_id`',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 兼容索引
SET @has_idx := (
  SELECT COUNT(1) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hr_employee_capability' AND INDEX_NAME = 'idx_cap_company_employee_work_type'
);
SET @sql := IF(
  @has_idx = 0,
  'ALTER TABLE `hr_employee_capability` ADD KEY `idx_cap_company_employee_work_type` (`company_id`, `employee_id`, `work_type_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx := (
  SELECT COUNT(1) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hr_employee_schedule_booking' AND INDEX_NAME = 'idx_booking_employee_work_type'
);
SET @sql := IF(
  @has_idx = 0,
  'ALTER TABLE `hr_employee_schedule_booking` ADD KEY `idx_booking_employee_work_type` (`employee_id`, `work_type_id`)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 先按历史 job_title / 部门名生成工种目录
INSERT INTO `hr_work_type` (`company_id`, `name`, `sort_order`, `is_active`, `remark`)
SELECT src.company_id, src.name, 0, 1, 'legacy auto backfill'
FROM (
  SELECT e.company_id AS company_id, TRIM(e.job_title) AS name
  FROM `hr_employee` e
  WHERE e.job_title IS NOT NULL AND TRIM(e.job_title) <> ''
  UNION
  SELECT d.company_id AS company_id, TRIM(d.name) AS name
  FROM `hr_department` d
  WHERE d.name IS NOT NULL AND TRIM(d.name) <> ''
) src
LEFT JOIN `hr_work_type` wt
  ON wt.company_id = src.company_id AND wt.name = src.name
WHERE src.company_id IS NOT NULL
  AND src.name IS NOT NULL
  AND src.name <> ''
  AND wt.id IS NULL;

-- 员工主工种：优先 job_title，其次同名部门
UPDATE `hr_employee` e
JOIN `hr_work_type` wt
  ON wt.company_id = e.company_id AND wt.name = TRIM(e.job_title)
SET e.main_work_type_id = wt.id
WHERE (e.main_work_type_id IS NULL OR e.main_work_type_id = 0)
  AND e.job_title IS NOT NULL
  AND TRIM(e.job_title) <> '';

UPDATE `hr_employee` e
JOIN `hr_department` d ON d.id = e.department_id
JOIN `hr_work_type` wt
  ON wt.company_id = e.company_id AND wt.name = TRIM(d.name)
SET e.main_work_type_id = wt.id
WHERE (e.main_work_type_id IS NULL OR e.main_work_type_id = 0)
  AND d.name IS NOT NULL
  AND TRIM(d.name) <> '';

-- 兼容回填：能力表 / 排产日志 / 计件单价 / 设备默认能力 / 生产资源统一补工种字段
UPDATE `hr_employee_capability` c
JOIN `hr_department` d ON d.id = c.hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET c.work_type_id = wt.id
WHERE (c.work_type_id IS NULL OR c.work_type_id = 0)
  AND c.hr_department_id IS NOT NULL
  AND c.hr_department_id > 0;

UPDATE `hr_employee_schedule_booking` b
JOIN `hr_employee` e ON e.id = b.employee_id
JOIN `hr_department` d ON d.id = b.hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = e.company_id AND wt.name = TRIM(d.name)
SET b.work_type_id = wt.id
WHERE (b.work_type_id IS NULL OR b.work_type_id = 0)
  AND b.hr_department_id IS NOT NULL
  AND b.hr_department_id > 0;

UPDATE `machine_type` mt
JOIN `hr_department` d ON d.id = mt.default_capability_hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET mt.default_capability_work_type_id = wt.id
WHERE mt.default_capability_work_type_id = 0
  AND mt.default_capability_hr_department_id > 0;

UPDATE `machine` m
JOIN `hr_department` d ON d.id = m.default_capability_hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET m.default_capability_work_type_id = wt.id
WHERE m.default_capability_work_type_id = 0
  AND m.default_capability_hr_department_id > 0;

UPDATE `machine_operator_allowlist` a
JOIN `hr_department` d ON d.id = a.capability_hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET a.capability_work_type_id = wt.id
WHERE a.capability_work_type_id = 0
  AND a.capability_hr_department_id > 0;

UPDATE `production_process_template_step` s
JOIN `hr_department` d ON d.id = s.hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET s.hr_work_type_id = wt.id
WHERE s.hr_work_type_id = 0
  AND s.hr_department_id > 0;

UPDATE `production_product_routing_step` s
JOIN `hr_department` d ON d.id = s.hr_department_id_override
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET s.hr_work_type_id_override = wt.id
WHERE s.hr_work_type_id_override = 0
  AND s.hr_department_id_override > 0;

UPDATE `production_process_node` n
JOIN `hr_department` d ON d.id = n.hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET n.hr_work_type_id = wt.id
WHERE n.hr_work_type_id = 0
  AND n.hr_department_id > 0;

UPDATE `production_routing_node_override` n
JOIN `hr_department` d ON d.id = n.hr_department_id_override
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET n.hr_work_type_id_override = wt.id
WHERE n.hr_work_type_id_override = 0
  AND n.hr_department_id_override > 0;

UPDATE `production_work_order_operation` op
JOIN `hr_department` d ON d.id = op.hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET op.hr_work_type_id = wt.id
WHERE op.hr_work_type_id = 0
  AND op.hr_department_id > 0;

UPDATE `production_work_order_operation_plan` op
JOIN `hr_department` d ON d.id = op.hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
SET op.hr_work_type_id = wt.id
WHERE op.hr_work_type_id = 0
  AND op.hr_department_id > 0;

INSERT INTO `hr_work_type_piece_rate` (
  `company_id`, `work_type_id`, `period`, `rate_per_unit`, `remark`, `created_by`, `created_at`, `updated_at`
)
SELECT p.company_id, wt.id, p.period, p.rate_per_unit, p.remark, p.created_by, p.created_at, p.updated_at
FROM `hr_department_piece_rate` p
JOIN `hr_department` d ON d.id = p.hr_department_id
JOIN `hr_work_type` wt
  ON wt.company_id = p.company_id AND wt.name = TRIM(d.name)
LEFT JOIN `hr_work_type_piece_rate` np
  ON np.company_id = p.company_id AND np.work_type_id = wt.id AND np.period = p.period
WHERE np.id IS NULL;

INSERT INTO `hr_department_work_type_map` (
  `company_id`, `department_id`, `work_type_id`, `is_active`, `remark`
)
SELECT d.company_id, d.id, wt.id, 1, 'legacy same-name mapping'
FROM `hr_department` d
JOIN `hr_work_type` wt
  ON wt.company_id = d.company_id AND wt.name = TRIM(d.name)
LEFT JOIN `hr_department_work_type_map` m
  ON m.company_id = d.company_id AND m.department_id = d.id AND m.work_type_id = wt.id
WHERE m.id IS NULL;

INSERT INTO `hr_employee_work_type` (`employee_id`, `work_type_id`, `is_primary`)
SELECT e.id, e.main_work_type_id, 1
FROM `hr_employee` e
LEFT JOIN `hr_employee_work_type` rel
  ON rel.employee_id = e.id AND rel.work_type_id = e.main_work_type_id
WHERE e.main_work_type_id IS NOT NULL
  AND e.main_work_type_id > 0
  AND rel.id IS NULL;

INSERT INTO `hr_employee_work_type` (`employee_id`, `work_type_id`, `is_primary`)
SELECT DISTINCT c.employee_id, c.work_type_id, 0
FROM `hr_employee_capability` c
LEFT JOIN `hr_employee_work_type` rel
  ON rel.employee_id = c.employee_id AND rel.work_type_id = c.work_type_id
WHERE c.work_type_id IS NOT NULL
  AND c.work_type_id > 0
  AND rel.id IS NULL;

INSERT INTO `hr_employee_work_type` (`employee_id`, `work_type_id`, `is_primary`)
SELECT DISTINCT b.employee_id, b.work_type_id, 0
FROM `hr_employee_schedule_booking` b
LEFT JOIN `hr_employee_work_type` rel
  ON rel.employee_id = b.employee_id AND rel.work_type_id = b.work_type_id
WHERE b.work_type_id IS NOT NULL
  AND b.work_type_id > 0
  AND rel.id IS NULL;

UPDATE `hr_employee_work_type` rel
JOIN `hr_employee` e ON e.id = rel.employee_id
SET rel.is_primary = CASE
  WHEN e.main_work_type_id IS NOT NULL AND rel.work_type_id = e.main_work_type_id THEN 1
  ELSE 0
END;

-- 导航 / 权限
SET @nav_hr_id = (SELECT `id` FROM `sys_nav_item` WHERE `code` = 'nav_hr' LIMIT 1);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_hr_id, 'hr_work_type', '工种管理', 'main.hr_work_type_list', 24, 1, 0, 1, 98)
ON DUPLICATE KEY UPDATE
  `parent_id` = VALUES(`parent_id`),
  `title` = VALUES(`title`),
  `endpoint` = VALUES(`endpoint`),
  `sort_order` = VALUES(`sort_order`),
  `is_active` = VALUES(`is_active`),
  `admin_only` = VALUES(`admin_only`),
  `is_assignable` = VALUES(`is_assignable`),
  `landing_priority` = VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
  ('hr_work_type.view', '工种：查看', 'hr_work_type', '人力资源', 240),
  ('hr_work_type.action.create', '工种：新建', 'hr_work_type', '人力资源', 241),
  ('hr_work_type.action.edit', '工种：编辑', 'hr_work_type', '人力资源', 242),
  ('hr_work_type.action.delete', '工种：删除', 'hr_work_type', '人力资源', 243)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

UPDATE `sys_nav_item`
SET `title` = '部门-工种允许关系'
WHERE `code` = 'hr_department_capability_map';

UPDATE `sys_capability`
SET `title` = CASE
  WHEN `code` = 'hr_department_capability_map.view' THEN '部门-工种允许关系：查看'
  WHEN `code` = 'hr_department_capability_map.edit' THEN '部门-工种允许关系：编辑'
  ELSE `title`
END
WHERE `code` IN ('hr_department_capability_map.view', 'hr_department_capability_map.edit');

UPDATE `sys_nav_item`
SET `title` = '工种计件单价'
WHERE `code` = 'dept_piece_rate';

UPDATE `sys_capability`
SET `title` = CASE
  WHEN `code` = 'dept_piece_rate.view' THEN '工种计件单价：查看'
  WHEN `code` = 'dept_piece_rate.edit' THEN '工种计件单价：编辑'
  ELSE `title`
END
WHERE `code` IN ('dept_piece_rate.view', 'dept_piece_rate.edit');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_work_type' FROM `role` r WHERE r.`code` = 'admin';

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, 'hr_work_type.view' FROM `role` r WHERE r.`code` = 'admin';
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, 'hr_work_type.action.create' FROM `role` r WHERE r.`code` = 'admin';
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, 'hr_work_type.action.edit' FROM `role` r WHERE r.`code` = 'admin';
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, 'hr_work_type.action.delete' FROM `role` r WHERE r.`code` = 'admin';
