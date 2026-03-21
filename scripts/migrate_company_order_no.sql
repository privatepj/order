-- 公司经营主体：订单号前缀、转月日
USE sydixon_order;

ALTER TABLE `company`
  ADD COLUMN `order_no_prefix` varchar(32) DEFAULT NULL COMMENT '订单号前缀' AFTER `code`,
  ADD COLUMN `billing_cycle_day` tinyint unsigned NOT NULL DEFAULT 1 COMMENT '转月日(1-31,1=自然月)' AFTER `order_no_prefix`;

UPDATE `company` SET `order_no_prefix` = `code` WHERE `order_no_prefix` IS NULL OR `order_no_prefix` = '';
