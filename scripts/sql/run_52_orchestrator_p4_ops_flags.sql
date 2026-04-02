-- P4: orchestrator operations flags
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_feature_flag` (`flag_key`, `flag_value`, `remark`)
VALUES
  ('orchestrator.replay_enabled', '1', '0=关闭 replay 接口与引擎重放能力'),
  ('orchestrator.retry_enabled', '1', '0=关闭失败动作自动/手动重试'),
  ('orchestrator.overdue_scan_enabled', '1', '0=关闭逾期扫描触发')
ON DUPLICATE KEY UPDATE
  `flag_value` = VALUES(`flag_value`),
  `remark` = VALUES(`remark`);
