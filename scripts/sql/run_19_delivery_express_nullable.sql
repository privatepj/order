-- 送货单：自配送时 express_company_id 为空（不占快递单号池）
USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `delivery`
  MODIFY COLUMN `express_company_id` int unsigned DEFAULT NULL COMMENT '快递公司；NULL 表示自配送';
