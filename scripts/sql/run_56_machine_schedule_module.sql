-- 机台排班模块（机台排班模板 / 排班展开时间窗；无 DB 外键）

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `machine_schedule_template` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `machine_id` int unsigned NOT NULL COMMENT '机台 machine.id',
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
  KEY `idx_ms_tpl_machine` (`machine_id`),
  KEY `idx_ms_tpl_valid` (`valid_from`,`valid_to`),
  KEY `idx_ms_tpl_state` (`state`),
  KEY `idx_ms_tpl_dow` (`days_of_week`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台排班模板（可重复）';

CREATE TABLE IF NOT EXISTS `machine_schedule_booking` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `machine_id` int unsigned NOT NULL COMMENT '机台 machine.id',
  `template_id` int unsigned NOT NULL COMMENT '机台排班模板 machine_schedule_template.id',
  `state` varchar(16) NOT NULL COMMENT 'available/unavailable',
  `start_at` datetime NOT NULL COMMENT '开始时间（分钟粒度）',
  `end_at` datetime NOT NULL COMMENT '结束时间（分钟粒度）',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL COMMENT '创建人 user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ms_booking_template_start` (`template_id`,`start_at`),
  KEY `idx_ms_booking_machine_start` (`machine_id`,`start_at`),
  KEY `idx_ms_booking_machine_end` (`machine_id`,`end_at`),
  KEY `idx_ms_booking_state_start` (`state`,`start_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台排班展开时间窗（可用/不可用）';

-- ----------------------------
-- RBAC：菜单 + 能力键 + warehouse 可访问
-- ----------------------------

SET @nav_machine_id := (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_machine' LIMIT 1);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_machine_id, 'machine_schedule', '机台排班', 'main.machine_schedule_template_list', 40, 1, 0, 1, 99)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('machine_schedule_template.action.create', '机台排班：模板新建', 'machine_schedule', '机台管理', 900),
('machine_schedule_template.action.edit', '机台排班：模板编辑', 'machine_schedule', '机台管理', 910),
('machine_schedule_template.action.delete', '机台排班：模板删除', 'machine_schedule', '机台管理', 920),
('machine_schedule_booking.action.create', '机台排班：时间窗新建/生成', 'machine_schedule', '机台管理', 930),
('machine_schedule_booking.action.edit', '机台排班：时间窗编辑', 'machine_schedule', '机台管理', 940),
('machine_schedule_booking.action.delete', '机台排班：时间窗删除', 'machine_schedule', '机台管理', 950)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'machine_schedule' FROM `role` r WHERE r.`code`='warehouse';

