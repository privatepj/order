-- 对账导出：经营主体联系/账户字段；客户传真
-- 可重复执行：先检查列是否存在（或由 run 脚本跳过重复）

ALTER TABLE `company`
  ADD COLUMN `phone` varchar(32) DEFAULT NULL COMMENT '电话' AFTER `billing_cycle_day`,
  ADD COLUMN `fax` varchar(32) DEFAULT NULL COMMENT '传真' AFTER `phone`,
  ADD COLUMN `address` varchar(255) DEFAULT NULL COMMENT '地址' AFTER `fax`,
  ADD COLUMN `contact_person` varchar(64) DEFAULT NULL COMMENT '联系人' AFTER `address`,
  ADD COLUMN `private_account` varchar(64) DEFAULT NULL COMMENT '对私账户' AFTER `contact_person`,
  ADD COLUMN `public_account` varchar(64) DEFAULT NULL COMMENT '对公账户' AFTER `private_account`,
  ADD COLUMN `account_name` varchar(64) DEFAULT NULL COMMENT '户名' AFTER `public_account`,
  ADD COLUMN `bank_name` varchar(128) DEFAULT NULL COMMENT '开户行' AFTER `account_name`,
  ADD COLUMN `preparer_name` varchar(64) DEFAULT NULL COMMENT '对账制表人' AFTER `bank_name`;

ALTER TABLE `customer`
  ADD COLUMN `fax` varchar(32) DEFAULT NULL COMMENT '传真' AFTER `phone`;
