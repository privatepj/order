-- Orchestrator P0: contracts/index enhancements
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `orchestrator_event`
  ADD KEY `idx_orch_event_type_status_occ` (`event_type`, `status`, `occurred_at`),
  ADD KEY `idx_orch_event_biz_occ` (`biz_key`, `occurred_at`);

ALTER TABLE `orchestrator_action`
  ADD KEY `idx_orch_action_status_retry` (`status`, `next_retry_at`),
  ADD KEY `idx_orch_action_event_status` (`event_id`, `status`);

ALTER TABLE `orchestrator_audit_log`
  ADD KEY `idx_orch_audit_event_created` (`event_id`, `created_at`);
