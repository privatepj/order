USE sydixon_order;
SET NAMES utf8mb4;
SET SESSION group_concat_max_len = 8192;

-- 停用的供应商或停用的供应关系不能继续作为默认供应商
UPDATE `supplier_material_map` sm
JOIN `supplier` s ON s.`id` = sm.`supplier_id`
SET sm.`is_preferred` = 0
WHERE sm.`is_preferred` = 1
  AND (sm.`is_active` = 0 OR s.`is_active` = 0);

-- 旧数据若同一主体+物料存在多个默认供应商，只保留最近更新时间最新、其次 id 最大的一条
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
