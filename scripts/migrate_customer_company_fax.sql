-- 客户传真、经营主体联系信息（旧库缺列时执行，列已存在会报错可忽略或用 run 脚本）
USE sydixon_order;

ALTER TABLE `customer`
  ADD COLUMN `fax` varchar(32) DEFAULT NULL COMMENT '传真' AFTER `phone`;

-- 以下按 init_db 顺序，若某列已存在请跳过该行或改用 Python 脚本
ALTER TABLE `company`
  ADD COLUMN `delivery_no_prefix` varchar(32) DEFAULT NULL COMMENT '送货单号前缀' AFTER `order_no_prefix`;

ALTER TABLE `company`
  ADD COLUMN `phone` varchar(32) DEFAULT NULL COMMENT '电话' AFTER `billing_cycle_day`;

ALTER TABLE `company`
  ADD COLUMN `fax` varchar(32) DEFAULT NULL COMMENT '传真' AFTER `phone`;

ALTER TABLE `company`
  ADD COLUMN `address` varchar(255) DEFAULT NULL COMMENT '地址' AFTER `fax`;

ALTER TABLE `company`
  ADD COLUMN `contact_person` varchar(64) DEFAULT NULL COMMENT '联系人' AFTER `address`;

ALTER TABLE `company`
  ADD COLUMN `private_account` varchar(64) DEFAULT NULL COMMENT '对私账户' AFTER `contact_person`;

ALTER TABLE `company`
  ADD COLUMN `public_account` varchar(64) DEFAULT NULL COMMENT '对公账户' AFTER `private_account`;

ALTER TABLE `company`
  ADD COLUMN `account_name` varchar(64) DEFAULT NULL COMMENT '户名' AFTER `public_account`;

ALTER TABLE `company`
  ADD COLUMN `bank_name` varchar(128) DEFAULT NULL COMMENT '开户行' AFTER `account_name`;

ALTER TABLE `company`
  ADD COLUMN `preparer_name` varchar(64) DEFAULT NULL COMMENT '对账制表人' AFTER `bank_name`;
