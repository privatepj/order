# 2026-04-28 `None` 字面量全链路清理（编辑页回显 `NONE`）

## 背景

- 多个编辑页在字段为空时出现 `NONE/None` 回显。
- 排查后确认不是前端硬编码，而是历史数据中存在字面量 `'None'`，且部分入库路径未统一做可选文本归一化。

## 变更内容

### 1) 全局模板回显兜底

- 在 `app/__init__.py` 注册 `app.jinja_env.finalize`，统一使用 `form_finalize`。
- `form_finalize` 规则：
  - `None -> ""`
  - 字符串在 `strip().lower()=="none"` 时 -> `""`
  - 其他类型保持原值（避免影响数值/日期表达式）。

### 2) 入库归一化统一（关键编辑链路）

- 统一复用 `clean_optional_text`，将 `""/空白/"none"(大小写不敏感)` 归一为 `None`。
- 覆盖本次高频问题链路：
  - 供应商新建/编辑/Excel导入相关文本字段（`routes_procurement.py`）。
  - 工资编辑备注（`routes_hr.py`）。
  - 工序模板/生产预排备注（`routes_production.py` 的 `_text_or_none` 与 `remark` 入库点）。
  - CRM 机会明细备注（`routes_crm.py`）。
  - 送货备注（`routes_delivery.py`）。

### 3) 历史数据清理 SQL

- 新增：`scripts/sql/run_92_cleanup_none_literal_optional_text.sql`
- 处理目标列（按 `LOWER(TRIM(col))='none'`）：
  - `supplier.contact_name/phone/address/remark`
  - `hr_payroll_line.remark`
  - `production_process_template.remark`
- 统一清理为 `NULL`，脚本可重复执行。

## 影响评估

- 不新增外部 API。
- 仅影响“可选文本”字段的显示与入库语义，业务必填/枚举逻辑不变。
- 通过全局 finalize，未逐页改模板也可消除历史 `'None'` 回显。

## 测试

- 扩展 `tests/test_form_display.py`：
  - `form_blank` 覆盖 `NONE`。
  - 新增 `form_finalize` 行为断言。
- 新增 `tests/test_none_sentinel_edit_pages.py`：
  - 供应商编辑页、工资编辑页、工序模板编辑页对历史 `'None'` 的回显断言为空。
