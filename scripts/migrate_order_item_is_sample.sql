-- 为订单明细增加“是否样品”标记（样品单价/金额按 0 处理）
ALTER TABLE `order_item`
  ADD COLUMN `is_sample` TINYINT(1) NOT NULL DEFAULT 0 AFTER `amount`;

