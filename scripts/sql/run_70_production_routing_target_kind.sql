-- 工序路由统一对象：支持成品/半成品
-- 约束：
-- - 不新增数据库级外键
-- - 兼容历史 product_id 路由数据，回填到 target_kind/target_id

USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `production_product_routing`
  ADD COLUMN `target_kind` varchar(16) NOT NULL DEFAULT 'finished' COMMENT '路由目标类型：finished/semi' AFTER `id`,
  ADD COLUMN `target_id` int unsigned NOT NULL DEFAULT 0 COMMENT '路由目标ID（成品=product.id，半成品=semi_material.id）' AFTER `target_kind`;

UPDATE `production_product_routing`
SET
  `target_kind` = 'finished',
  `target_id` = `product_id`
WHERE (`target_id` IS NULL OR `target_id` = 0) AND `product_id` > 0;

ALTER TABLE `production_product_routing`
  DROP INDEX `uk_prod_routing_product`,
  ADD UNIQUE KEY `uk_prod_routing_target` (`target_kind`, `target_id`),
  ADD KEY `idx_prod_routing_product` (`product_id`);
