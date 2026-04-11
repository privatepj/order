# 预计划人工排程与确认同步

- **路由**：`POST /production/preplans/<id>/schedule-manual`、`POST /production/preplans/<id>/schedule-confirm`（`routes_production.py`）。
- **服务**：`app/services/production_preplan_schedule_manual_svc.py`；人员可用窗 `hr_employee_schedule_svc.is_employee_available`。
- **SQL**：`scripts/sql/run_71_production_operation_plan_commit.sql`（`production_work_order_operation_plan` 确认列 + `production_schedule_commit_row`）；全量见 `00_full_schema.sql`。
- **测算**：`measure_production_for_preplan` 前若存在已报工 dispatch 则抛错；否则先 `revoke_preplan_commits_for_measure`。
