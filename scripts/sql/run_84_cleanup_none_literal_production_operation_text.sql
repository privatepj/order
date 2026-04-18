-- 历史数据：工序快照曾将 Python None 写成字面量 'None'，纠正为语义上的空。
UPDATE production_work_order_operation
SET step_name = ''
WHERE step_name IN ('None', 'none');

UPDATE production_work_order_operation
SET step_code = NULL
WHERE step_code IN ('None', 'none');
