-- 生产事故表 + 生产管理导航改为分组（预生产计划 / 生产事故）
-- 无外键约束；存量库执行后重启应用或 invalidate_rbac_cache()

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `production_incident` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `incident_no` varchar(32) DEFAULT NULL COMMENT '事故编号（唯一，可空后由系统补全）',
  `title` varchar(255) NOT NULL COMMENT '标题',
  `occurred_at` datetime NOT NULL COMMENT '发生时间',
  `workshop` varchar(128) DEFAULT NULL COMMENT '车间/地点',
  `severity` varchar(32) DEFAULT NULL COMMENT '严重程度',
  `status` varchar(16) NOT NULL DEFAULT 'open' COMMENT 'open/closed',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注/D0 计划摘要',
  `d1_team` text COMMENT 'D1 小组',
  `d2_problem` text COMMENT 'D2 问题描述',
  `d3_containment` text COMMENT 'D3 临时措施',
  `d4_root_cause` text COMMENT 'D4 根本原因',
  `d5_corrective` text COMMENT 'D5 永久纠正措施',
  `d6_implementation` text COMMENT 'D6 实施与验证',
  `d7_prevention` text COMMENT 'D7 预防再发',
  `d8_recognition` text COMMENT 'D8 总结与表彰',
  `created_by` int unsigned NOT NULL COMMENT 'user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_production_incident_no` (`incident_no`),
  KEY `idx_production_incident_occurred` (`occurred_at`),
  KEY `idx_production_incident_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生产事故与 8D';

-- 父节点：分组（无 endpoint）
UPDATE `sys_nav_item`
SET `endpoint` = NULL,
    `is_assignable` = 0,
    `landing_priority` = NULL
WHERE `code` = 'production';

-- 子菜单：预生产计划、生产事故
INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
)
SELECT p.`id`, 'production_preplan', '预生产计划', 'main.production_preplan_list', 10,
       1, 0, 1, 87
FROM `sys_nav_item` p WHERE p.`code` = 'production' LIMIT 1
ON DUPLICATE KEY UPDATE
  `parent_id` = VALUES(`parent_id`),
  `title` = VALUES(`title`),
  `endpoint` = VALUES(`endpoint`),
  `sort_order` = VALUES(`sort_order`),
  `admin_only` = VALUES(`admin_only`),
  `is_assignable` = VALUES(`is_assignable`),
  `landing_priority` = VALUES(`landing_priority`);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
)
SELECT p.`id`, 'production_incident', '生产事故', 'main.production_incident_list', 20,
       1, 0, 1, 88
FROM `sys_nav_item` p WHERE p.`code` = 'production' LIMIT 1
ON DUPLICATE KEY UPDATE
  `parent_id` = VALUES(`parent_id`),
  `title` = VALUES(`title`),
  `endpoint` = VALUES(`endpoint`),
  `sort_order` = VALUES(`sort_order`),
  `admin_only` = VALUES(`admin_only`),
  `is_assignable` = VALUES(`is_assignable`),
  `landing_priority` = VALUES(`landing_priority`);

-- 预生产相关能力归属叶子 production_preplan
UPDATE `sys_capability`
SET `nav_item_code` = 'production_preplan',
    `group_label` = '预生产计划'
WHERE `nav_item_code` = 'production';

-- 生产事故能力
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('production_incident.filter.keyword', '生产事故：关键词筛选', 'production_incident', '生产事故', 10),
('production_incident.action.create', '生产事故：新建', 'production_incident', '生产事故', 20),
('production_incident.action.edit', '生产事故：编辑', 'production_incident', '生产事故', 30),
('production_incident.action.delete', '生产事故：删除', 'production_incident', '生产事故', 40),
('production_incident.report.8d', '生产事故：8D 报告（打印/导出）', 'production_incident', '生产事故', 50)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

-- 角色菜单：原 production 拆成两个子菜单
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT `role_id`, 'production_preplan' FROM `role_allowed_nav` WHERE `nav_code` = 'production';

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT `role_id`, 'production_incident' FROM `role_allowed_nav` WHERE `nav_code` = 'production';

DELETE FROM `role_allowed_nav` WHERE `nav_code` = 'production';

-- 兼容仍使用 allowed_menu_keys JSON 的角色（未走 role_allowed_nav 时）
UPDATE `role`
SET `allowed_menu_keys` = CAST(
  REPLACE(CAST(`allowed_menu_keys` AS CHAR CHARSET utf8mb4), '"production"', '"production_preplan","production_incident"')
  AS JSON
)
WHERE `allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(`allowed_menu_keys`) = 'ARRAY'
  AND JSON_CONTAINS(`allowed_menu_keys`, '"production"', '$');
