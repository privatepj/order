-- CRM 模块：线索/机会/工单（无 FOREIGN KEY 逻辑外键）
USE sydixon_order;
SET NAMES utf8mb4;

-- ----------------------------
-- 线索
-- ----------------------------
CREATE TABLE IF NOT EXISTS `crm_lead` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `lead_code` varchar(64) NOT NULL,
  `customer_id` int unsigned DEFAULT NULL,
  `customer_name` varchar(128) NOT NULL,
  `contact` varchar(64) DEFAULT NULL,
  `phone` varchar(32) DEFAULT NULL,
  `source` varchar(64) NOT NULL DEFAULT 'manual',
  `status` varchar(32) NOT NULL DEFAULT 'new',
  `tags` varchar(255) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_crm_lead_code` (`lead_code`),
  KEY `idx_crm_lead_customer_id` (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- 机会
-- ----------------------------
CREATE TABLE IF NOT EXISTS `crm_opportunity` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `opp_code` varchar(64) NOT NULL,
  `lead_id` int unsigned DEFAULT NULL,
  `customer_id` int unsigned NOT NULL,
  `stage` varchar(32) NOT NULL DEFAULT 'draft',
  `expected_amount` decimal(26,8) DEFAULT NULL,
  `currency` varchar(16) DEFAULT NULL,
  `expected_close_date` date DEFAULT NULL,
  `salesperson` varchar(64) NOT NULL DEFAULT 'GaoMeiHua',
  `customer_order_no` varchar(64) DEFAULT NULL,
  `order_date` date DEFAULT NULL,
  `required_date` date DEFAULT NULL,
  `payment_type` varchar(16) NOT NULL DEFAULT 'monthly',
  `remark` varchar(255) DEFAULT NULL,
  `tags` varchar(255) DEFAULT NULL,
  `won_order_id` int unsigned DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_crm_opportunity_code` (`opp_code`),
  KEY `idx_crm_opp_lead_id` (`lead_id`),
  KEY `idx_crm_opp_customer_id` (`customer_id`),
  KEY `idx_crm_opp_stage` (`stage`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- 机会产品行
-- ----------------------------
CREATE TABLE IF NOT EXISTS `crm_opportunity_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `opportunity_id` int unsigned NOT NULL,
  `customer_product_id` int unsigned NOT NULL,
  `quantity` decimal(26,8) NOT NULL DEFAULT 0,
  `is_sample` tinyint(1) NOT NULL DEFAULT 0,
  `is_spare` tinyint(1) NOT NULL DEFAULT 0,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_crm_opp_line` (`opportunity_id`, `customer_product_id`),
  KEY `idx_crm_opp_line_opp_id` (`opportunity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- 工单
-- ----------------------------
CREATE TABLE IF NOT EXISTS `crm_ticket` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `ticket_code` varchar(64) NOT NULL,
  `customer_id` int unsigned NOT NULL,
  `ticket_type` varchar(64) NOT NULL DEFAULT 'support',
  `priority` varchar(32) NOT NULL DEFAULT 'normal',
  `status` varchar(32) NOT NULL DEFAULT 'open',
  `subject` varchar(128) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `assignee_user_id` int unsigned DEFAULT NULL,
  `due_date` date DEFAULT NULL,
  `tags` varchar(255) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `won_order_id` int unsigned DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_crm_ticket_code` (`ticket_code`),
  KEY `idx_crm_ticket_customer_id` (`customer_id`),
  KEY `idx_crm_ticket_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- 工单活动记录
-- ----------------------------
CREATE TABLE IF NOT EXISTS `crm_ticket_activity` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `ticket_id` int unsigned NOT NULL,
  `actor_user_id` int unsigned DEFAULT NULL,
  `activity_type` varchar(64) NOT NULL DEFAULT 'note',
  `content` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_crm_ticket_activity_ticket_id` (`ticket_id`),
  KEY `idx_crm_ticket_activity_actor_user_id` (`actor_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

