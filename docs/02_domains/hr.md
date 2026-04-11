# 业务域：人力（HR）

> 本文档为**骨架**。

## 核心概念

- 部门、工种、员工、排班、能力/计件、工资等：`app/models/hr.py`。
- 服务：`hr_work_type_svc.py`、`hr_employee_schedule_svc.py`、`hr_employee_capability_svc.py` 等。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_hr.py`、`routes_employee_schedule.py`、`routes_employee_capability.py` |
| 模板 | `app/templates/hr/*.html` |
| 生产协作 | 员工排班/能力与工单关联（见 `HrEmployeeScheduleBooking` 等） |

## 权限

- 以各路由文件装饰器为准；变更时同步项目 Skill 映射表。
