USE sydixon_order;
SET NAMES utf8mb4;
SET SESSION group_concat_max_len = 8192;

-- 停用供应商或停用映射不能继续作为默认供应商
UPDATE `supplier_material_map` sm
JOIN `supplier` s ON s.`id` = sm.`supplier_id`
SET sm.`is_preferred` = 0
WHERE sm.`is_preferred` = 1
  AND (sm.`is_active` = 0 OR s.`is_active` = 0);

-- 同一主体同一物料只保留一条默认供应商，按更新时间最新、其次 id 最大保留
UPDATE `supplier_material_map` sm
JOIN (
  SELECT
    `company_id`,
    `material_id`,
    CAST(
      SUBSTRING_INDEX(
        GROUP_CONCAT(`id` ORDER BY `updated_at` DESC, `id` DESC),
        ',',
        1
      ) AS UNSIGNED
    ) AS `keep_id`
  FROM `supplier_material_map`
  WHERE `is_preferred` = 1
  GROUP BY `company_id`, `material_id`
  HAVING COUNT(1) > 1
) keepers
  ON keepers.`company_id` = sm.`company_id`
 AND keepers.`material_id` = sm.`material_id`
SET sm.`is_preferred` = CASE
  WHEN sm.`id` = keepers.`keep_id` THEN 1
  ELSE 0
END
WHERE sm.`is_preferred` = 1;

SET @nav_procurement_id = (
  SELECT `id` FROM `sys_nav_item` WHERE `code` = 'nav_procurement' LIMIT 1
);

INSERT INTO `sys_nav_item` (
  `parent_id`, `code`, `title`, `endpoint`, `sort_order`,
  `is_active`, `admin_only`, `is_assignable`, `landing_priority`
) VALUES
  (@nav_procurement_id, 'procurement_material', '物料管理', 'main.procurement_material_list', 4, 1, 0, 1, 100)
ON DUPLICATE KEY UPDATE
  `parent_id` = VALUES(`parent_id`),
  `title` = VALUES(`title`),
  `endpoint` = VALUES(`endpoint`),
  `sort_order` = VALUES(`sort_order`),
  `admin_only` = VALUES(`admin_only`),
  `is_assignable` = VALUES(`is_assignable`),
  `landing_priority` = VALUES(`landing_priority`);

UPDATE `sys_nav_item`
SET `title` = '半成品'
WHERE `code` = 'semi_material';

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('procurement_material.filter.keyword', '物料管理：关键词', 'procurement_material', '采购管理', 875),
('procurement_material.action.create', '物料管理：新建', 'procurement_material', '采购管理', 876),
('procurement_material.action.edit', '物料管理：编辑', 'procurement_material', '采购管理', 877),
('procurement_material.action.delete', '物料管理：删除', 'procurement_material', '采购管理', 878),
('procurement_material.action.import', '物料管理：Excel 导入', 'procurement_material', '采购管理', 879)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);

UPDATE `sys_capability`
SET `title` = CASE `code`
  WHEN 'semi_material.filter.keyword' THEN '半成品列表：关键词搜索'
  WHEN 'semi_material.action.create' THEN '半成品：新建主数据'
  WHEN 'semi_material.action.edit' THEN '半成品：编辑主数据'
  WHEN 'semi_material.action.delete' THEN '半成品：删除主数据'
  WHEN 'semi_material.action.import' THEN '半成品：Excel 导入'
  ELSE `title`
END
WHERE `nav_item_code` = 'semi_material';

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_material' FROM `role` r WHERE r.`code` = 'warehouse';
