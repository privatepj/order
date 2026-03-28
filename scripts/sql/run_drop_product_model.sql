-- 若库中曾添加过 product.model，执行本脚本删除该列。
-- 列不存在时报错可忽略。

USE sydixon_order;
ALTER TABLE `product` DROP COLUMN `model`;
