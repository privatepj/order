# 业务数值统一 8 位小数（decimal(26,8)）

## 数据库

- 新增增量脚本 [`scripts/sql/run_76_decimal_scale_8.sql`](../../scripts/sql/run_76_decimal_scale_8.sql)：将订单、库存、生产、采购、HR、机台、调度器等相关列改为 `decimal(26,8)`；`hr_work_type_piece_rate` / `hr_department_piece_rate` 存在时一并修改。
- 全量定义已同步 [`scripts/sql/00_full_schema.sql`](../../scripts/sql/00_full_schema.sql)。

## 应用

- 新增 [`app/utils/decimal_scale.py`](../../app/utils/decimal_scale.py)：`quantize_decimal`、`json_decimal`（对外 JSON 字符串，去无意义尾随零）、`to_decimal`。
- ORM：`app/models` 中业务 `Numeric` 列统一为 `Numeric(26, 8)`。
- 计算与导出：`OrderItem.compute_amount`、排程工时、对账/送货 Excel、采购单模板填充等改为量化或 `Decimal` 路径，避免中间 `float` 截断。
- OpenClaw `pending-items` 数量类字段改为字符串十进制；`delivery_svc` 预览行、订单预览摘要使用 `json_decimal`。

## 前端

- 业务数字输入框 `step` 调整为 `0.00000001`（打印缩放等非业务控件除外）。

## 测试

- [`tests/test_procurement_workflow.py`](../../tests/test_procurement_workflow.py) 等与单价字符串展示相关的断言已按 `json_decimal` 规范化结果调整。
