-- P2: recovery and replay observability
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `orchestrator_replay_job` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `event_id` bigint unsigned NOT NULL COMMENT 'logic ref orchestrator_event.id',
  `dry_run` tinyint(1) NOT NULL DEFAULT 0,
  `allow_high_risk` tinyint(1) NOT NULL DEFAULT 0,
  `selected_actions` json DEFAULT NULL,
  `blocked_actions` json DEFAULT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'done',
  `created_by` int unsigned DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_orch_replay_job_event` (`event_id`),
  KEY `idx_orch_replay_job_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Orchestrator条件重放任务日志';

ALTER TABLE `orchestrator_action`
  ADD KEY `idx_orch_action_status_type` (`status`, `action_type`);
