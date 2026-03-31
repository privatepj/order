-- 机台管理模块：表 + 导航 + 能力 + 角色菜单
-- 无外键约束；应用层保证关联语义

USE sydixon_order;
SET NAMES utf8mb4;

DROP TABLE IF EXISTS `machine_runtime_log`;
DROP TABLE IF EXISTS `machine`;
DROP TABLE IF EXISTS `machine_type`;

CREATE TABLE `machine_type` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `code` varchar(32) NOT NULL COMMENT '机台种类编码',
  `name` varchar(64) NOT NULL COMMENT '机台种类名称',
  `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '1=启用 0=停用',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_machine_type_code` (`code`),
  UNIQUE KEY `uk_machine_type_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台种类';

CREATE TABLE `machine` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `machine_no` varchar(32) NOT NULL COMMENT '机台编号',
  `name` varchar(64) NOT NULL COMMENT '机台名称',
  `machine_type_id` int unsigned NOT NULL COMMENT '机台种类 machine_type.id',
  `capacity_per_hour` decimal(12,2) NOT NULL DEFAULT 0.00 COMMENT '标准产能（件/小时）',
  `status` varchar(16) NOT NULL DEFAULT 'enabled' COMMENT 'enabled/disabled/maintenance/scrapped',
  `location` varchar(128) DEFAULT NULL COMMENT '车间/产线',
  `owner_user_id` int unsigned DEFAULT NULL COMMENT '责任人 user.id',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_machine_no` (`machine_no`),
  KEY `idx_machine_type` (`machine_type_id`),
  KEY `idx_machine_status` (`status`),
  KEY `idx_machine_owner` (`owner_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台台账';

CREATE TABLE `machine_runtime_log` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `machine_id` int unsigned NOT NULL COMMENT '机台 machine.id',
  `runtime_status` varchar(16) NOT NULL COMMENT 'running/idle/fault',
  `started_at` datetime NOT NULL COMMENT '开始时间',
  `ended_at` datetime DEFAULT NULL COMMENT '结束时间，NULL=进行中',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL COMMENT '录入人 user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_machine_runtime_machine` (`machine_id`),
  KEY `idx_machine_runtime_started` (`started_at`),
  KEY `idx_machine_runtime_open` (`machine_id`,`ended_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台运转情况记录';

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (NULL, 'nav_machine', '机台管理', NULL, 16, 1, 0, 0, NULL)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

SET @nav_machine_id = (SELECT `id` FROM `sys_nav_item` WHERE `code`='nav_machine' LIMIT 1);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_machine_id, 'machine_type', '机台种类', 'main.machine_type_list', 10, 1, 0, 1, 96),
  (@nav_machine_id, 'machine_asset', '机台台账', 'main.machine_list', 20, 1, 0, 1, 97),
  (@nav_machine_id, 'machine_runtime', '运转情况', 'main.machine_runtime_list', 30, 1, 0, 1, 98)
ON DUPLICATE KEY UPDATE
  `parent_id`=VALUES(`parent_id`),
  `title`=VALUES(`title`),
  `endpoint`=VALUES(`endpoint`),
  `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`),
  `is_assignable`=VALUES(`is_assignable`),
  `landing_priority`=VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('machine_type.action.create', '机台种类：新建', 'machine_type', '机台管理', 600),
('machine_type.action.edit', '机台种类：编辑', 'machine_type', '机台管理', 610),
('machine_type.action.delete', '机台种类：删除', 'machine_type', '机台管理', 620),
('machine_asset.filter.keyword', '机台台账：关键词', 'machine_asset', '机台管理', 700),
('machine_asset.action.create', '机台台账：新建', 'machine_asset', '机台管理', 710),
('machine_asset.action.edit', '机台台账：编辑', 'machine_asset', '机台管理', 720),
('machine_asset.action.delete', '机台台账：删除', 'machine_asset', '机台管理', 730),
('machine_runtime.action.create', '机台运转：新建记录', 'machine_runtime', '机台管理', 800),
('machine_runtime.action.edit', '机台运转：编辑记录', 'machine_runtime', '机台管理', 810),
('machine_runtime.action.close', '机台运转：结束记录', 'machine_runtime', '机台管理', 820)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'machine_type' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'machine_asset' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'machine_runtime' FROM `role` r WHERE r.`code`='warehouse';
