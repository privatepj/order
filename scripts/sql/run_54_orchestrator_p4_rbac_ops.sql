-- P4: orchestrator ops capability hardening
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('orchestrator.replay.high_risk', '编排引擎：高风险重放', 'production_preplan', '编排引擎运维', 510),
('orchestrator.recover.batch', '编排引擎：批量恢复死信', 'production_preplan', '编排引擎运维', 520),
('orchestrator.metric.write', '编排引擎：写 AI 指标评估', 'production_preplan', '编排引擎运维', 530)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

-- run_54 used non-existent column `capability_key`; actual column is `cap_code`
-- keep idempotent behavior with INSERT IGNORE
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, c.`code`
FROM `role` r
JOIN `sys_capability` c ON c.`code` IN ('orchestrator.recover.batch', 'orchestrator.metric.write')
WHERE r.`code` = 'warehouse';
