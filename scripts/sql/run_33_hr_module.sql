-- 人力资源模块：表 + 导航 + 能力 + 财务角色菜单
-- 无外键约束；存量库执行本脚本后重启应用或 invalidate_rbac_cache()

USE sydixon_order;
SET NAMES utf8mb4;

DROP TABLE IF EXISTS `hr_performance_review`;
DROP TABLE IF EXISTS `hr_payroll_line`;
DROP TABLE IF EXISTS `hr_employee`;
DROP TABLE IF EXISTS `hr_department`;
CREATE TABLE `hr_department` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `name` varchar(128) NOT NULL COMMENT '部门名称',
  `sort_order` int NOT NULL DEFAULT 0,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hr_dept_company_name` (`company_id`,`name`),
  KEY `idx_hr_dept_company` (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HR 部门';

CREATE TABLE `hr_employee` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `department_id` int unsigned DEFAULT NULL COMMENT 'hr_department.id',
  `user_id` int unsigned DEFAULT NULL COMMENT '可选关联登录用户 user.id',
  `employee_no` varchar(32) NOT NULL COMMENT '工号',
  `name` varchar(64) NOT NULL,
  `id_card` varchar(32) DEFAULT NULL COMMENT '身份证（敏感）',
  `phone` varchar(32) DEFAULT NULL,
  `job_title` varchar(64) DEFAULT NULL COMMENT '岗位',
  `status` varchar(16) NOT NULL DEFAULT 'active' COMMENT 'active=在职 left=离职',
  `hire_date` date DEFAULT NULL,
  `leave_date` date DEFAULT NULL,
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hr_emp_company_no` (`company_id`,`employee_no`),
  KEY `idx_hr_emp_company` (`company_id`),
  KEY `idx_hr_emp_dept` (`department_id`),
  KEY `idx_hr_emp_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HR 人员档案';

CREATE TABLE `hr_payroll_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL COMMENT 'hr_employee.id',
  `period` char(7) NOT NULL COMMENT '账期 YYYY-MM',
  `base_salary` decimal(14,2) NOT NULL DEFAULT 0.00,
  `allowance` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '津贴',
  `deduction` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '扣款',
  `net_pay` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '实发',
  `remark` varchar(500) DEFAULT NULL,
  `created_by` int unsigned NOT NULL COMMENT 'user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hr_pay_company_emp_period` (`company_id`,`employee_id`,`period`),
  KEY `idx_hr_pay_company_period` (`company_id`,`period`),
  KEY `idx_hr_pay_employee` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HR 工资明细（按月一行）';

CREATE TABLE `hr_performance_review` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `cycle` varchar(32) NOT NULL COMMENT '考核周期 如 2026-Q1',
  `score` decimal(6,2) DEFAULT NULL,
  `comment` text COMMENT '评语',
  `reviewer_user_id` int unsigned DEFAULT NULL COMMENT '考核人 user.id',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft=草稿 finalized=已定稿',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hr_perf_company_emp_cycle` (`company_id`,`employee_id`,`cycle`),
  KEY `idx_hr_perf_company` (`company_id`),
  KEY `idx_hr_perf_employee` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HR 绩效考核';

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (NULL, 'nav_hr', '人力资源', NULL, 17, 1, 0, 0, NULL)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

SET @nav_hr_id = (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_hr' LIMIT 1);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_hr_id, 'hr_department', '部门', 'main.hr_department_list', 10, 1, 0, 1, 92),
  (@nav_hr_id, 'hr_employee', '人员档案', 'main.hr_employee_list', 20, 1, 0, 1, 93),
  (@nav_hr_id, 'hr_payroll', '工资录入', 'main.hr_payroll_list', 30, 1, 0, 1, 94),
  (@nav_hr_id, 'hr_performance', '绩效管理', 'main.hr_performance_list', 40, 1, 0, 1, 95)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('hr_department.filter.keyword', 'HR 部门：关键词', 'hr_department', '人力资源', 200),
('hr_department.action.create', 'HR 部门：新建', 'hr_department', '人力资源', 210),
('hr_department.action.edit', 'HR 部门：编辑', 'hr_department', '人力资源', 220),
('hr_department.action.delete', 'HR 部门：删除', 'hr_department', '人力资源', 230),
('hr_employee.filter.company', 'HR 人员：按主体筛选', 'hr_employee', '人力资源', 300),
('hr_employee.filter.keyword', 'HR 人员：关键词', 'hr_employee', '人力资源', 310),
('hr_employee.action.create', 'HR 人员：新建', 'hr_employee', '人力资源', 320),
('hr_employee.action.edit', 'HR 人员：编辑', 'hr_employee', '人力资源', 330),
('hr_employee.action.delete', 'HR 人员：删除', 'hr_employee', '人力资源', 340),
('hr_employee.action.import', 'HR 人员：Excel 导入', 'hr_employee', '人力资源', 350),
('hr_employee.action.export_template', 'HR 人员：下载导入模板', 'hr_employee', '人力资源', 360),
('hr_employee.view_sensitive', 'HR 人员：查看身份证/完整手机', 'hr_employee', '人力资源', 370),
('hr_payroll.view', 'HR 工资：查看', 'hr_payroll', '人力资源', 400),
('hr_payroll.edit', 'HR 工资：录入与修改', 'hr_payroll', '人力资源', 410),
('hr_payroll.export', 'HR 工资：导出 Excel', 'hr_payroll', '人力资源', 420),
('hr_performance.action.create', 'HR 绩效：新建', 'hr_performance', '人力资源', 500),
('hr_performance.action.edit', 'HR 绩效：编辑', 'hr_performance', '人力资源', 510),
('hr_performance.action.delete', 'HR 绩效：删除', 'hr_performance', '人力资源', 520),
('hr_performance.action.finalize', 'HR 绩效：定稿', 'hr_performance', '人力资源', 530),
('hr_performance.action.override', 'HR 绩效：已定稿后修改', 'hr_performance', '人力资源', 540)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_department' FROM `role` r WHERE r.`code`='finance';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_employee' FROM `role` r WHERE r.`code`='finance';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_payroll' FROM `role` r WHERE r.`code`='finance';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_performance' FROM `role` r WHERE r.`code`='finance';
