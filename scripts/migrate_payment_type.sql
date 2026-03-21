-- 订单付款类型：月结 / 现金 / 样板
USE sydixon_order;

ALTER TABLE `sales_order`
  ADD COLUMN `payment_type` varchar(16) NOT NULL DEFAULT 'monthly'
  COMMENT 'monthly=月结 cash=现金 sample=样板' AFTER `status`;
