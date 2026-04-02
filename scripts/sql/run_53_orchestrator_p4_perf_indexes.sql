-- P4: orchestrator performance indexes
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `orchestrator_event`
  ADD KEY `idx_orch_event_status_processed` (`status`, `processed_at`);

ALTER TABLE `orchestrator_action`
  ADD KEY `idx_orch_action_status_updated` (`status`, `updated_at`),
  ADD KEY `idx_orch_action_created_event` (`created_at`, `event_id`);

ALTER TABLE `orchestrator_replay_job`
  ADD KEY `idx_orch_replay_status_created` (`status`, `created_at`);
