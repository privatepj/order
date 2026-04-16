# CRM 模块（客户管理）初始设计与落地规划

## 背景与目标
在现有系统已有“客户（`Customer`）/客户产品（`CustomerProduct`）/订单（`SalesOrder`）”基础上，补齐一套 CRM 模块，用于管理客户的线索、机会与服务工单，并支持“机会成交后生成订单”的业务打通。

## 现有能力复用（不重造）
- 客户主数据：`app/models/customer.py` 与对应路由 `app/main/routes_customer.py`
- 客户产品：`app/models/product.py` 中 `CustomerProduct` 与路由 `app/main/routes_customer_product.py`
- 订单创建：`app/services/order_svc.py` 的 `create_order_from_data(data)`
  - CRM 机会->订单映射核心依赖 `customer_product_id + quantity + is_sample/is_spare`

## CRM 新增实体（最小可落地集）
1. 线索（Lead）：`CrmLead`
   - 主要字段：`lead_code`、`customer_id(逻辑外键)`、`customer_name`、`contact/phone`、`status/source/tags/remark`
2. 机会（Opportunity）：`CrmOpportunity`
   - 主要字段：`opp_code`、`lead_id(逻辑外键)`、`customer_id`、`stage`、`expected_amount/currency/expected_close_date`、订单相关默认字段（`customer_order_no/order_date/required_date/payment_type`）等
3. 机会产品行（OpportunityLine）：`CrmOpportunityLine`
   - 主要字段：`opportunity_id`、`customer_product_id`、`quantity`、`is_sample`、`is_spare`
4. 工单（Ticket）：`CrmTicket`
   - 主要字段：`ticket_code`、`customer_id`、`ticket_type/priority/status`、`subject/description`、`assignee_user_id(逻辑外键)`、`due_date` 等
5. 工单活动记录（TicketActivity）：`CrmTicketActivity`
   - 主要字段：`ticket_id`、`actor_user_id(逻辑外键)`、`activity_type`、`content`、`created_at`

## 状态流转与关键动作
### Opportunity（机会）
- `draft -> qualified -> negotiating -> won/lost`
- `won` 前必须至少存在一行机会产品行，且数量必须 > 0
- 关键动作：当生成订单成功后，将机会标记为 `won` 并写入 `won_order_id`

### Ticket（工单）
- `open -> in_progress -> resolved -> closed`
- 关键动作：通过活动（`TicketActivity`）记录处理过程，并可将工单状态通过 `/set-status` 路由推进

## 机会->订单映射（集成点）
调用：`app/services/order_svc.py:create_order_from_data(data)`
数据组装规则：
- `data.customer_id = opportunity.customer_id`
- `data.items = opportunity.lines[].{ customer_product_id, quantity, is_sample, is_spare }`
- 订单号/日期/付款类型/销售员/备注：来自“生成订单”表单（优先）或机会默认字段

## 路由/API 与 RBAC
路由文件：`app/main/routes_crm.py`
主要页面与能力码：
- 菜单叶子：`crm_lead` / `crm_opportunity` / `crm_ticket`
- 能力码：
  - `crm_lead.action.create/edit/delete`
  - `crm_opportunity.action.create/edit/generate_order`
  - `crm_ticket.action.create/edit/delete`
实现方式：
- `app/auth/capability_data.py` + `app/auth/menus.py` 提供无种子兜底
- 生产库建议通过增量脚本加入 `sys_nav_item / sys_capability / role_allowed_nav`

## SQL 与测试
新增增量脚本：
- `scripts/sql/run_80_crm_module_tables.sql`：建 CRM 表
- `scripts/sql/run_81_crm_module_nav_caps.sql`：补齐导航菜单、细项能力与角色默认可见性

新增测试：
- `tests/test_crm_opportunity_generate_order.py`
  - 覆盖：没有产品行时 `qualified -> won` 失败
  - 覆盖：机会生成订单并将机会标记为 `won`，同时校验订单明细（样板/备品 price=0 逻辑）

## 实施与回滚建议
- 先部署增量 SQL（run_80/run_81）
- 再部署应用代码
- 回滚：删除新增 CRM 表需要数据迁移/归档，不建议直接回滚；通常按业务切换开关（若需要可在后续版本补 feature flag）

