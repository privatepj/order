-- 移除库内遗留的数据库级外键（本项目规范：全库不使用 FOREIGN KEY）
-- 幂等：通过 information_schema 判断后再执行 DROP（兼容 MySQL，无 IF EXISTS 语法）
USE sydixon_order;
SET NAMES utf8mb4;

-- sys_nav_item 自引用父节点（历史 run_15 / 旧全量脚本曾创建 fk_nav_parent）
SET @sql_drop_fk = (
  SELECT IF(
    COUNT(*) > 0,
    'ALTER TABLE `sys_nav_item` DROP FOREIGN KEY `fk_nav_parent`',
    'SELECT 1 AS `_skip_no_fk`'
  )
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND TABLE_NAME = 'sys_nav_item'
    AND CONSTRAINT_NAME = 'fk_nav_parent'
    AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);
PREPARE _stmt_run23 FROM @sql_drop_fk;
EXECUTE _stmt_run23;
DEALLOCATE PREPARE _stmt_run23;
