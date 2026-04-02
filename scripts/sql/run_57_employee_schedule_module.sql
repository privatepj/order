-- 人员排产模块（人员排班模板 / 排产时间窗 + 工作log；无 DB 外键）

USE sydixon_order;
SET NAMES utf8mb4;

-- ----------------------------
-- 人员排班（模板可重复）
-- ----------------------------
CREATE TABLE IF NOT EXISTS `hr_employee_schedule_template` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `employee_id` int unsigned NOT NULL COMMENT '人员 hr_employee.id',
  `name` varchar(64) NOT NULL COMMENT '排班模板名称',
  `repeat_kind` varchar(16) NOT NULL DEFAULT 'weekly' COMMENT '重复类型：weekly',
  `days_of_week` varchar(32) NOT NULL COMMENT '星期列表（0=周日..6=周六），逗号分隔',
  `valid_from` date NOT NULL COMMENT '有效起始日期',
  `valid_to` date DEFAULT NULL COMMENT '有效结束日期，NULL=长期',
  `start_time` time NOT NULL COMMENT '每天开始时间',
  `end_time` time NOT NULL COMMENT '每天结束时间；若 <= start_time 则表示跨日',
  `state` varchar(16) NOT NULL COMMENT 'available/unavailable',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL COMMENT '创建人 user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_hes_tpl_employee` (`employee_id`),
  KEY `idx_hes_tpl_valid` (`valid_from`,`valid_to`),
  KEY `idx_hes_tpl_state` (`state`),
  KEY `idx_hes_tpl_dow` (`days_of_week`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人员排班模板（可重复）';

-- ----------------------------
-- 时间窗（排产展开）+ 工作log字段
-- ----------------------------
CREATE TABLE IF NOT EXISTS `hr_employee_schedule_booking` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `employee_id` int unsigned NOT NULL COMMENT '人员 hr_employee.id',
  `template_id` int unsigned NOT NULL COMMENT '人员排班模板 hr_employee_schedule_template.id',
  `state` varchar(16) NOT NULL COMMENT 'available/unavailable',
  `start_at` datetime NOT NULL COMMENT '开始时间（分钟粒度）',
  `end_at` datetime NOT NULL COMMENT '结束时间（分钟粒度）',
  `remark` varchar(255) DEFAULT NULL COMMENT '排产/工时/工单备注（应用层约定口径）',
  `created_by` int unsigned NOT NULL COMMENT '创建人 user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  -- 工作log（手工维护；应用层保证一致性）
  `hr_department_id` int unsigned DEFAULT NULL COMMENT '工位 hr_department.id（应用层约定）',
  `work_order_id` int unsigned DEFAULT NULL COMMENT '生产工单 production_work_order.id',
  `product_id` int unsigned DEFAULT NULL COMMENT '成品 product.id（由 work_order_id 推导；成品才写入）',
  `unit` varchar(16) DEFAULT NULL COMMENT '单位（由 product.base_unit 回填）',
  `good_qty` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT '良品数量',
  `bad_qty` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT '不良数量',
  `produced_qty` decimal(18,4) NOT NULL DEFAULT 0.0000 COMMENT '总产出（good+bad）',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hes_booking_template_start` (`template_id`,`start_at`),
  KEY `idx_hes_booking_employee_start` (`employee_id`,`start_at`),
  KEY `idx_hes_booking_employee_end` (`employee_id`,`end_at`),
  KEY `idx_hes_booking_state_start` (`state`,`start_at`),
  KEY `idx_hes_booking_department` (`hr_department_id`),
  KEY `idx_hes_booking_work_order` (`work_order_id`),
  KEY `idx_hes_booking_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人员排产时间窗（可用/不可用）与工作log';

-- ----------------------------
-- RBAC：菜单 + 能力键 + warehouse 可访问
-- ----------------------------
SET @nav_hr_id := (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_hr' LIMIT 1);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_hr_id, 'hr_employee_schedule', '人员排产', 'main.hr_employee_schedule_template_list', 55, 1, 0, 1, 95)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('hr_employee_schedule_template.action.create', '人员排产：模板新建', 'hr_employee_schedule', '人力资源', 600),
('hr_employee_schedule_template.action.edit', '人员排产：模板编辑', 'hr_employee_schedule', '人力资源', 610),
('hr_employee_schedule_template.action.delete', '人员排产：模板删除', 'hr_employee_schedule', '人力资源', 620),
('hr_employee_schedule_booking.action.create', '人员排产：时间窗新建/生成', 'hr_employee_schedule', '人力资源', 630),
('hr_employee_schedule_booking.action.edit', '人员排产：时间窗编辑', 'hr_employee_schedule', '人力资源', 640),
('hr_employee_schedule_booking.action.delete', '人员排产：时间窗删除', 'hr_employee_schedule', '人力资源', 650)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_employee_schedule' FROM `role` r WHERE r.`code`='warehouse';

