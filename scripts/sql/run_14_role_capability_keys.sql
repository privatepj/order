-- 角色表：细项能力（按钮、筛选项等），与 app/auth/capabilities.py 对应
-- 执行前请备份。若列已存在可忽略 Duplicate column 错误。

USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `role`
  ADD COLUMN `allowed_capability_keys` json DEFAULT NULL COMMENT '细项能力 key 的 JSON 数组；NULL/[] 表示在已选菜单内默认全开' AFTER `allowed_menu_keys`;
