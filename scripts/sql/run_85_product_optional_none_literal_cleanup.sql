-- 产品可选字段曾误存 Python None 的字面量 'None'，纠正为 NULL。
UPDATE product
SET spec = NULL
WHERE spec IS NOT NULL AND LOWER(TRIM(spec)) = 'none';

UPDATE product
SET base_unit = NULL
WHERE base_unit IS NOT NULL AND LOWER(TRIM(base_unit)) = 'none';

UPDATE product
SET remark = NULL
WHERE remark IS NOT NULL AND LOWER(TRIM(remark)) = 'none';
