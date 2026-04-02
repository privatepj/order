-- P2: orchestrator rules seed
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `orchestrator_rule_profile` (
  `rule_code`, `rule_name`, `allow_alternative`, `allow_outsource`, `allow_secondary_supplier`, `priority`, `is_active`, `extra_json`
) VALUES
  ('default_shortage', '默认缺料策略', 1, 1, 1, 100, 1, JSON_OBJECT('note', 'P2 default')),
  ('strict_shortage', '严格缺料策略', 0, 1, 0, 200, 1, JSON_OBJECT('note', 'No alternative by default'))
ON DUPLICATE KEY UPDATE
  `rule_name`=VALUES(`rule_name`),
  `allow_alternative`=VALUES(`allow_alternative`),
  `allow_outsource`=VALUES(`allow_outsource`),
  `allow_secondary_supplier`=VALUES(`allow_secondary_supplier`),
  `priority`=VALUES(`priority`),
  `is_active`=VALUES(`is_active`),
  `extra_json`=VALUES(`extra_json`);
