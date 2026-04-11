USE sydixon_order;
SET NAMES utf8mb4;

SET @production_nav_id := (
  SELECT `id` FROM `sys_nav_item` WHERE `code` = 'production' LIMIT 1
);

UPDATE `sys_nav_item`
SET
  `parent_id` = @production_nav_id,
  `sort_order` = 30
WHERE `code` = 'machine_schedule'
  AND @production_nav_id IS NOT NULL;

UPDATE `sys_nav_item`
SET
  `parent_id` = @production_nav_id,
  `sort_order` = 40
WHERE `code` = 'hr_employee_schedule'
  AND @production_nav_id IS NOT NULL;
