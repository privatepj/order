-- P3: orchestrator feature flags
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `sys_feature_flag` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `flag_key` varchar(64) NOT NULL,
  `flag_value` varchar(255) NOT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sys_feature_flag_key` (`flag_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统功能开关';

INSERT INTO `sys_feature_flag` (`flag_key`, `flag_value`, `remark`)
VALUES
  ('orchestrator.kill_switch', '0', '1=关闭执行，仅保留事件入库'),
  ('orchestrator.company_whitelist', '', '逗号分隔 company_id'),
  ('orchestrator.biz_key_whitelist', '', '逗号分隔 biz_key')
ON DUPLICATE KEY UPDATE
  `flag_value` = VALUES(`flag_value`),
  `remark` = VALUES(`remark`);
