-- 菜单与能力库表 + 角色授权关联表（与 app/models/rbac.py 一致）
-- 执行前备份。若表已存在可跳过或手动删除后重跑。

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `sys_nav_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `parent_id` int unsigned DEFAULT NULL,
  `code` varchar(64) NOT NULL,
  `title` varchar(128) NOT NULL,
  `endpoint` varchar(128) DEFAULT NULL COMMENT 'Flask endpoint，如 main.order_list',
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `admin_only` tinyint(1) NOT NULL DEFAULT 0 COMMENT '仅 admin 角色可分配',
  `is_assignable` tinyint(1) NOT NULL DEFAULT 1 COMMENT '0=仅导航分组节点',
  `landing_priority` int DEFAULT NULL COMMENT '越小越优先作为登录落地页',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_nav_code` (`code`),
  KEY `idx_nav_parent` (`parent_id`),
  CONSTRAINT `fk_nav_parent` FOREIGN KEY (`parent_id`) REFERENCES `sys_nav_item` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='导航菜单项';

CREATE TABLE IF NOT EXISTS `sys_capability` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `code` varchar(128) NOT NULL,
  `title` varchar(255) NOT NULL,
  `nav_item_code` varchar(64) NOT NULL COMMENT '归属菜单叶子 code',
  `group_label` varchar(128) NOT NULL DEFAULT '',
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cap_code` (`code`),
  KEY `idx_cap_nav` (`nav_item_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='细项能力';

CREATE TABLE IF NOT EXISTS `role_allowed_nav` (
  `role_id` int unsigned NOT NULL,
  `nav_code` varchar(64) NOT NULL,
  PRIMARY KEY (`role_id`, `nav_code`),
  KEY `idx_ran_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色可访问菜单';

CREATE TABLE IF NOT EXISTS `role_allowed_capability` (
  `role_id` int unsigned NOT NULL,
  `cap_code` varchar(128) NOT NULL,
  PRIMARY KEY (`role_id`, `cap_code`),
  KEY `idx_rac_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色显式细项能力白名单';
