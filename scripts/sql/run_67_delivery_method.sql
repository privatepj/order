-- 送货单新增显式配送方式：快递 / 自配送 / 自提

ALTER TABLE `delivery`
  ADD COLUMN `delivery_method` varchar(16) NOT NULL DEFAULT 'express' COMMENT 'express/self_delivery/pickup' AFTER `customer_id`;

UPDATE `delivery`
SET `delivery_method` = CASE
  WHEN `express_company_id` IS NOT NULL THEN 'express'
  ELSE 'self_delivery'
END
WHERE `delivery_method` NOT IN ('express', 'self_delivery', 'pickup')
   OR `delivery_method` IS NULL
   OR `delivery_method` = '';
