-- 经营主体：默认主体 is_default（company.is_default）
-- 无外键约束；增量脚本仅追加新语义，不修改既有 run_* 文件。
USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `company`
  ADD COLUMN `is_default` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否默认主体';
