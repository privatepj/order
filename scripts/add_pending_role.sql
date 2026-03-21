-- 为已有数据库添加「待分配」角色（注册功能需要）
-- 若 init_db.sql 已包含该条则无需执行
INSERT INTO `role` (`name`, `code`, `description`)
SELECT '待分配', 'pending', '注册后等待管理员分配'
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM `role` WHERE `code` = 'pending');
