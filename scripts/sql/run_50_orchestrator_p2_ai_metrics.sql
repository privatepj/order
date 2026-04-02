-- P2: AI advice adoption metrics
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `orchestrator_ai_advice_metric` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `advice_id` bigint unsigned NOT NULL COMMENT 'logic ref orchestrator_ai_advice.id',
  `event_id` bigint unsigned NOT NULL COMMENT 'logic ref orchestrator_event.id',
  `advice_type` varchar(64) NOT NULL,
  `is_adopted` tinyint(1) NOT NULL DEFAULT 0,
  `adopted_latency_seconds` int DEFAULT NULL,
  `result_score` decimal(9,4) DEFAULT NULL,
  `metric_note` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_orch_ai_metric_event` (`event_id`),
  KEY `idx_orch_ai_metric_type_adopted` (`advice_type`, `is_adopted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Orchestrator AI建议采纳评估明细';
