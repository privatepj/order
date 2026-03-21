-- 为 user 表增加 requested_role_id 字段，用于保存用户申请的目标角色
ALTER TABLE `user`
    ADD COLUMN `requested_role_id` int unsigned NULL AFTER `role_id`;

-- 为 requested_role_id 建索引，便于按待审批用户查询
ALTER TABLE `user`
    ADD KEY `idx_requested_role_id` (`requested_role_id`);
