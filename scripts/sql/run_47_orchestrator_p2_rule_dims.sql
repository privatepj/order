-- P2: orchestrator rules dimensions
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `orchestrator_rule_profile` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `rule_code` varchar(64) NOT NULL,
  `rule_name` varchar(128) NOT NULL,
  `allow_alternative` tinyint(1) NOT NULL DEFAULT 0,
  `allow_outsource` tinyint(1) NOT NULL DEFAULT 0,
  `allow_secondary_supplier` tinyint(1) NOT NULL DEFAULT 0,
  `priority` int NOT NULL DEFAULT 100,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `extra_json` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_orch_rule_code` (`rule_code`),
  KEY `idx_orch_rule_active_priority` (`is_active`, `priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Orchestrator规则画像';
