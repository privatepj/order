-- 将 customer_product.material_no 与关联产品的 product_code 对齐（一次性修正历史数据）。
-- 不创建外键；仅 UPDATE。执行前请备份。

UPDATE `customer_product` AS cp
INNER JOIN `product` AS p ON cp.`product_id` = p.`id`
SET cp.`material_no` = p.`product_code`;
