-- 调度引擎：事件、动作、审计、AI建议
-- 规则：仅逻辑关联，不使用 FOREIGN KEY

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `orchestrator_event` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `event_type` varchar(64) NOT NULL COMMENT '事件类型',
  `biz_key` varchar(128) NOT NULL COMMENT '业务键，如 order:123',
  `trace_id` varchar(64) DEFAULT NULL COMMENT '链路跟踪',
  `idempotency_key` varchar(128) NOT NULL COMMENT '幂等键',
  `payload` json DEFAULT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'new' COMMENT 'new/processing/done/failed',
  `error_message` varchar(500) DEFAULT NULL,
  `attempts` int NOT NULL DEFAULT 0,
  `occurred_at` datetime NOT NULL,
  `processed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_orch_event_idempotency` (`idempotency_key`),
  KEY `idx_orch_event_type` (`event_type`),
  KEY `idx_orch_event_biz_key` (`biz_key`),
  KEY `idx_orch_event_trace` (`trace_id`),
  KEY `idx_orch_event_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调度引擎事件';

CREATE TABLE IF NOT EXISTS `orchestrator_action` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `event_id` bigint unsigned NOT NULL COMMENT '关联 orchestrator_event.id（逻辑外键）',
  `action_type` varchar(64) NOT NULL COMMENT '动作类型',
  `action_key` varchar(128) NOT NULL COMMENT '动作幂等键',
  `payload` json DEFAULT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/done/failed/dead',
  `retry_count` int NOT NULL DEFAULT 0,
  `next_retry_at` datetime DEFAULT NULL,
  `error_message` varchar(500) DEFAULT NULL,
  `executed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_orch_action_key` (`action_key`),
  KEY `idx_orch_action_event` (`event_id`),
  KEY `idx_orch_action_type` (`action_type`),
  KEY `idx_orch_action_status` (`status`),
  KEY `idx_orch_action_next_retry` (`next_retry_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调度引擎动作';

CREATE TABLE IF NOT EXISTS `orchestrator_audit_log` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `event_id` bigint unsigned DEFAULT NULL COMMENT '关联 orchestrator_event.id（逻辑外键）',
  `action_id` bigint unsigned DEFAULT NULL COMMENT '关联 orchestrator_action.id（逻辑外键）',
  `level` varchar(16) NOT NULL DEFAULT 'info',
  `message` varchar(500) NOT NULL,
  `detail` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_orch_audit_event` (`event_id`),
  KEY `idx_orch_audit_action` (`action_id`),
  KEY `idx_orch_audit_level` (`level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调度引擎审计日志';

CREATE TABLE IF NOT EXISTS `orchestrator_ai_advice` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `event_id` bigint unsigned NOT NULL COMMENT '关联 orchestrator_event.id（逻辑外键）',
  `advice_type` varchar(64) NOT NULL COMMENT '建议类型',
  `recommended_action` varchar(128) NOT NULL COMMENT '建议动作',
  `confidence` decimal(5,4) DEFAULT NULL COMMENT '置信度 0-1',
  `reason` varchar(1000) DEFAULT NULL COMMENT '建议理由',
  `meta` json DEFAULT NULL,
  `is_adopted` tinyint(1) NOT NULL DEFAULT 0,
  `adopted_by` int unsigned DEFAULT NULL COMMENT '采纳人 user.id（逻辑外键）',
  `adopted_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_orch_advice_event` (`event_id`),
  KEY `idx_orch_advice_adopted` (`is_adopted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='调度引擎AI建议';
