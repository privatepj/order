-- 历史数据清理：将可选文本字段误存的字面量 'None' / 'none' 归一为 NULL
-- 规则：仅处理 LOWER(TRIM(col))='none'，脚本可重复执行

UPDATE supplier
SET contact_name = NULL
WHERE contact_name IS NOT NULL AND LOWER(TRIM(contact_name)) = 'none';

UPDATE supplier
SET phone = NULL
WHERE phone IS NOT NULL AND LOWER(TRIM(phone)) = 'none';

UPDATE supplier
SET address = NULL
WHERE address IS NOT NULL AND LOWER(TRIM(address)) = 'none';

UPDATE supplier
SET remark = NULL
WHERE remark IS NOT NULL AND LOWER(TRIM(remark)) = 'none';

UPDATE hr_payroll_line
SET remark = NULL
WHERE remark IS NOT NULL AND LOWER(TRIM(remark)) = 'none';

UPDATE production_process_template
SET remark = NULL
WHERE remark IS NOT NULL AND LOWER(TRIM(remark)) = 'none';
