-- 生产管理：导航「顶级化」数据修正（从曾误并入 run_31 的内容拆出）
-- 语义与 run_32_production_nav_root.sql 一致；若已执行过 run_32，本脚本可跳过（幂等）。
-- 无外键约束；部署后请重启应用或调用 invalidate_rbac_cache()。

USE sydixon_order;
SET NAMES utf8mb4;

UPDATE `sys_nav_item`
SET `parent_id` = NULL, `sort_order` = 15
WHERE `code` = 'production';
