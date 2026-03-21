-- 从旧库升级：公司表、客户经营主体与税点、客户产品物料编号（执行一次，请先备份）
USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `company` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '主体名称',
  `code` varchar(32) NOT NULL COMMENT '短码',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='经营主体';

INSERT INTO `company` (`name`, `code`)
SELECT '经营主体A', 'A' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `company` WHERE `code` = 'A');
INSERT INTO `company` (`name`, `code`)
SELECT '经营主体B', 'B' FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM `company` WHERE `code` = 'B');

-- 以下 ALTER 若列已存在会报错，请仅执行一次
ALTER TABLE `customer`
  ADD COLUMN `company_id` int unsigned NULL COMMENT '经营主体' AFTER `remark`,
  ADD COLUMN `tax_point` decimal(6,4) DEFAULT NULL COMMENT '税率如0.13' AFTER `company_id`;

UPDATE `customer` c
SET `company_id` = (SELECT MIN(id) FROM `company`)
WHERE c.`company_id` IS NULL;

ALTER TABLE `customer`
  MODIFY `company_id` int unsigned NOT NULL,
  ADD KEY `idx_company_id` (`company_id`);

ALTER TABLE `customer_product`
  ADD COLUMN `material_no` varchar(64) DEFAULT NULL COMMENT '物料编号' AFTER `customer_material_no`;
