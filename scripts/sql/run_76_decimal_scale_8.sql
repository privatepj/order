-- 业务数值列统一为 decimal(26,8)（小数点后 8 位）
-- 说明：不修改历史 run_*.sql；新环境以 00_full_schema.sql 为准。
USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `customer` MODIFY COLUMN `tax_point` decimal(26,8) DEFAULT NULL COMMENT '税率小数如0.13';

ALTER TABLE `semi_material` MODIFY COLUMN `standard_unit_cost` decimal(26,8) DEFAULT NULL COMMENT '标准单位成本（元/单位；预算用）';

ALTER TABLE `bom_line` MODIFY COLUMN `quantity` decimal(26,8) NOT NULL DEFAULT 0;

ALTER TABLE `production_preplan_line` MODIFY COLUMN `quantity` decimal(26,8) NOT NULL DEFAULT 0;

ALTER TABLE `production_work_order`
  MODIFY COLUMN `demand_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '根需求推导出的总需求',
  MODIFY COLUMN `stock_covered_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '库存覆盖数量（计算时点）',
  MODIFY COLUMN `to_produce_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '需要生产的净数量';

ALTER TABLE `production_component_need`
  MODIFY COLUMN `required_qty` decimal(26,8) NOT NULL DEFAULT 0,
  MODIFY COLUMN `stock_covered_qty` decimal(26,8) NOT NULL DEFAULT 0,
  MODIFY COLUMN `shortage_qty` decimal(26,8) NOT NULL DEFAULT 0;

ALTER TABLE `production_process_template_step`
  MODIFY COLUMN `setup_minutes` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '准备/换型时间（分钟）',
  MODIFY COLUMN `run_minutes_per_unit` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '单位运行时间（分钟/件）';

ALTER TABLE `production_product_routing_step`
  MODIFY COLUMN `setup_minutes_override` decimal(26,8) DEFAULT NULL COMMENT '准备时间覆写（分钟）',
  MODIFY COLUMN `run_minutes_per_unit_override` decimal(26,8) DEFAULT NULL COMMENT '单位运行时间覆写（分钟/件）';

ALTER TABLE `production_work_order_operation`
  MODIFY COLUMN `plan_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '用于计算的工序数量（快照）',
  MODIFY COLUMN `setup_minutes` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '工序准备时间（快照）',
  MODIFY COLUMN `run_minutes_per_unit` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '工序运行时间/单位（快照）',
  MODIFY COLUMN `estimated_setup_minutes` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '预计准备时间',
  MODIFY COLUMN `estimated_run_minutes` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '预计运行时间',
  MODIFY COLUMN `estimated_total_minutes` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '预计总工时（分钟）';

ALTER TABLE `production_process_node`
  MODIFY COLUMN `setup_minutes` decimal(26,8) DEFAULT NULL COMMENT '准备时间（可覆写）',
  MODIFY COLUMN `run_minutes_per_unit` decimal(26,8) DEFAULT NULL COMMENT '单位运行时间（可覆写）',
  MODIFY COLUMN `scrap_rate` decimal(26,8) DEFAULT NULL COMMENT '报废/损耗率（0-1，可选）';

ALTER TABLE `production_routing_node_override`
  MODIFY COLUMN `setup_minutes_override` decimal(26,8) DEFAULT NULL,
  MODIFY COLUMN `run_minutes_per_unit_override` decimal(26,8) DEFAULT NULL,
  MODIFY COLUMN `scrap_rate_override` decimal(26,8) DEFAULT NULL;

ALTER TABLE `production_work_order_operation_plan`
  MODIFY COLUMN `planned_minutes` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '排程工时（分钟）';

ALTER TABLE `production_material_plan_detail`
  MODIFY COLUMN `required_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '理论需求量',
  MODIFY COLUMN `scrap_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '损耗/报废量',
  MODIFY COLUMN `net_required_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '净需求量',
  MODIFY COLUMN `stock_covered_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '库存覆盖量（重算后）',
  MODIFY COLUMN `shortage_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '最终缺口';

ALTER TABLE `production_cost_plan_detail`
  MODIFY COLUMN `amount` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '成本金额',
  MODIFY COLUMN `unit_cost` decimal(26,8) DEFAULT NULL COMMENT '单位成本（可选）',
  MODIFY COLUMN `qty_basis` decimal(26,8) DEFAULT NULL COMMENT '成本计量数量（如工时/用量）';

ALTER TABLE `customer_product` MODIFY COLUMN `price` decimal(26,8) DEFAULT NULL COMMENT '单价';

ALTER TABLE `order_item`
  MODIFY COLUMN `quantity` decimal(26,8) NOT NULL DEFAULT 0,
  MODIFY COLUMN `price` decimal(26,8) DEFAULT NULL,
  MODIFY COLUMN `amount` decimal(26,8) DEFAULT NULL COMMENT '该行总金额';

ALTER TABLE `delivery_item` MODIFY COLUMN `quantity` decimal(26,8) NOT NULL DEFAULT 0;

ALTER TABLE `inventory_daily_line` MODIFY COLUMN `quantity` decimal(26,8) NOT NULL DEFAULT 0;

ALTER TABLE `inventory_opening_balance` MODIFY COLUMN `opening_qty` decimal(26,8) NOT NULL DEFAULT 0;

ALTER TABLE `inventory_movement` MODIFY COLUMN `quantity` decimal(26,8) NOT NULL;

ALTER TABLE `inventory_reservation` MODIFY COLUMN `reserved_qty` decimal(26,8) NOT NULL DEFAULT 0;

ALTER TABLE `hr_payroll_line`
  MODIFY COLUMN `work_hours` decimal(26,8) DEFAULT NULL COMMENT '换算时薪/产能成本所用工时（小时；月薪口径可填）',
  MODIFY COLUMN `hourly_rate` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '时薪（元/小时；小时口径使用）',
  MODIFY COLUMN `base_salary` decimal(26,8) NOT NULL DEFAULT 0,
  MODIFY COLUMN `allowance` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '津贴',
  MODIFY COLUMN `deduction` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '扣款',
  MODIFY COLUMN `net_pay` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '实发';

ALTER TABLE `hr_performance_review` MODIFY COLUMN `score` decimal(26,8) DEFAULT NULL;

ALTER TABLE `machine`
  MODIFY COLUMN `capacity_per_hour` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '标准产能（件/小时）',
  MODIFY COLUMN `machine_cost_purchase_price` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '购入价格（管理员维护）',
  MODIFY COLUMN `machine_accum_produced_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '机台累计生产个数',
  MODIFY COLUMN `machine_accum_runtime_hours` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '机台累计运行时长（小时）',
  MODIFY COLUMN `machine_single_run_cost` decimal(26,8) DEFAULT NULL COMMENT '机台单次运行成本（管理员维护）';

ALTER TABLE `machine_schedule_dispatch_log`
  MODIFY COLUMN `planned_runtime_hours` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '计划运行时长（小时）',
  MODIFY COLUMN `actual_produced_qty` decimal(26,8) DEFAULT NULL COMMENT '实际产量（个）',
  MODIFY COLUMN `actual_runtime_hours` decimal(26,8) DEFAULT NULL COMMENT '实际运行时长（小时）';

ALTER TABLE `hr_employee_schedule_booking`
  MODIFY COLUMN `good_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '良品数量',
  MODIFY COLUMN `bad_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '不良数量',
  MODIFY COLUMN `produced_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '总产出（good+bad）';

ALTER TABLE `hr_employee_capability`
  MODIFY COLUMN `good_qty_total` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '累计良品数量',
  MODIFY COLUMN `bad_qty_total` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '累计不良数量',
  MODIFY COLUMN `produced_qty_total` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '累计总产出（good+bad）',
  MODIFY COLUMN `worked_minutes_total` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '累计工时（分钟；用于小时产能/成本）',
  MODIFY COLUMN `labor_cost_total` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '累计劳动力成本（用于单件成本）';

ALTER TABLE `purchase_requisition` MODIFY COLUMN `qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '请购数量';

ALTER TABLE `purchase_order`
  MODIFY COLUMN `qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '采购数量',
  MODIFY COLUMN `unit_price` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '单价',
  MODIFY COLUMN `amount` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '金额';

ALTER TABLE `purchase_receipt` MODIFY COLUMN `received_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '收货数量';

ALTER TABLE `purchase_stock_in`
  MODIFY COLUMN `qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '入库数量',
  MODIFY COLUMN `received_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '收货数量',
  MODIFY COLUMN `warehouse_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '仓库确认数量',
  MODIFY COLUMN `variance_qty` decimal(26,8) NOT NULL DEFAULT 0 COMMENT '差异数量';

ALTER TABLE `orchestrator_ai_advice` MODIFY COLUMN `confidence` decimal(26,8) DEFAULT NULL COMMENT '置信度 0-1';

ALTER TABLE `orchestrator_ai_advice_metric` MODIFY COLUMN `result_score` decimal(26,8) DEFAULT NULL;

ALTER TABLE `supplier_material_map` MODIFY COLUMN `last_unit_price` decimal(26,8) DEFAULT NULL;

ALTER TABLE `purchase_requisition_line` MODIFY COLUMN `qty` decimal(26,8) NOT NULL DEFAULT 0;

SET @has_wtpr := (
  SELECT COUNT(1) FROM information_schema.TABLES
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hr_work_type_piece_rate'
);
SET @sql_wtpr := IF(
  @has_wtpr > 0,
  'ALTER TABLE `hr_work_type_piece_rate` MODIFY COLUMN `rate_per_unit` decimal(26,8) NOT NULL DEFAULT 0 COMMENT ''元/件''',
  'SELECT 1'
);
PREPARE stmt_wtpr FROM @sql_wtpr;
EXECUTE stmt_wtpr;
DEALLOCATE PREPARE stmt_wtpr;

SET @has_dpr := (
  SELECT COUNT(1) FROM information_schema.TABLES
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hr_department_piece_rate'
);
SET @sql_dpr := IF(
  @has_dpr > 0,
  'ALTER TABLE `hr_department_piece_rate` MODIFY COLUMN `rate_per_unit` decimal(26,8) NOT NULL DEFAULT 0 COMMENT ''元/件''',
  'SELECT 1'
);
PREPARE stmt_dpr FROM @sql_dpr;
EXECUTE stmt_dpr;
DEALLOCATE PREPARE stmt_dpr;
