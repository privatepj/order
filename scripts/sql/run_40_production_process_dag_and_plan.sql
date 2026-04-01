-- 生产工序二期：工序DAG与测算结果表
-- 说明：
-- - 不使用数据库级外键，仅通过列 + 索引表达关联语义。
-- - 若全量 schema 已同步这些表，本脚本在新库执行时等效；在老库执行用于增量添加。

USE sydixon_order;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `production_process_node` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `template_id` int unsigned NOT NULL COMMENT '关联 production_process_template.id（逻辑外键）',
  `parent_node_id` int unsigned DEFAULT NULL COMMENT '父节点（用于工序组层级，可为空）',
  `step_no` int unsigned DEFAULT NULL COMMENT '可选：对应模板步骤号，用于与现有 step 对齐',
  `node_type` varchar(16) NOT NULL DEFAULT 'operation' COMMENT 'operation=基础工序 group=工序组',
  `code` varchar(64) DEFAULT NULL COMMENT '节点编码',
  `name` varchar(128) NOT NULL COMMENT '节点名称',
  `resource_kind` varchar(16) DEFAULT NULL COMMENT '资源维度：machine_type/hr_department，允许为空表示继承',
  `machine_type_id` int unsigned NOT NULL DEFAULT 0 COMMENT '资源=machine_type 时使用',
  `hr_department_id` int unsigned NOT NULL DEFAULT 0 COMMENT '资源=hr_department 时使用',
  `setup_minutes` decimal(12,2) DEFAULT NULL COMMENT '准备时间（可覆写）',
  `run_minutes_per_unit` decimal(12,4) DEFAULT NULL COMMENT '单位运行时间（可覆写）',
  `scrap_rate` decimal(8,4) DEFAULT NULL COMMENT '报废/损耗率（0-1，可选）',
  `remark` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_proc_node_template` (`template_id`),
  KEY `idx_proc_node_parent` (`parent_node_id`),
  KEY `idx_proc_node_type` (`template_id`,`node_type`),
  KEY `idx_proc_node_step` (`template_id`,`step_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工序图节点（支持多层级与工序组）';

CREATE TABLE IF NOT EXISTS `production_process_edge` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `template_id` int unsigned NOT NULL COMMENT '所属模板（冗余便于查询）',
  `from_node_id` int unsigned NOT NULL COMMENT '前置节点',
  `to_node_id` int unsigned NOT NULL COMMENT '后继节点',
  `edge_type` varchar(16) NOT NULL DEFAULT 'fs' COMMENT 'fs=Finish-Start ff=Finish-Finish ss=Start-Start',
  `lag_minutes` int DEFAULT 0 COMMENT '时差（分钟，可正负，默认0）',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_proc_edge` (`from_node_id`,`to_node_id`,`edge_type`),
  KEY `idx_proc_edge_template` (`template_id`),
  KEY `idx_proc_edge_to` (`to_node_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工序依赖边（DAG）';

CREATE TABLE IF NOT EXISTS `production_routing_node_override` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `routing_id` int unsigned NOT NULL COMMENT '关联 production_product_routing.id（逻辑外键）',
  `process_node_id` int unsigned NOT NULL COMMENT '被覆写的工序节点',
  `resource_kind_override` varchar(16) DEFAULT NULL COMMENT '资源维度覆写',
  `machine_type_id_override` int unsigned NOT NULL DEFAULT 0,
  `hr_department_id_override` int unsigned NOT NULL DEFAULT 0,
  `setup_minutes_override` decimal(12,2) DEFAULT NULL,
  `run_minutes_per_unit_override` decimal(12,4) DEFAULT NULL,
  `scrap_rate_override` decimal(8,4) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_routing_node` (`routing_id`,`process_node_id`),
  KEY `idx_routing_node_routing` (`routing_id`),
  KEY `idx_routing_node_proc` (`process_node_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品级工序节点覆写（资源/工时/损耗）';

CREATE TABLE IF NOT EXISTS `production_work_order_operation_plan` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `work_order_id` int unsigned NOT NULL,
  `operation_id` int unsigned NOT NULL COMMENT '关联 production_work_order_operation.id（逻辑外键）',
  `process_node_id` int unsigned DEFAULT NULL COMMENT '可选：关联工序节点，用于追溯 DAG',
  `plan_date` date NOT NULL COMMENT '计划日期（冗余）',
  `es` datetime DEFAULT NULL COMMENT 'Earliest Start',
  `ef` datetime DEFAULT NULL COMMENT 'Earliest Finish',
  `ls` datetime DEFAULT NULL COMMENT 'Latest Start（预留）',
  `lf` datetime DEFAULT NULL COMMENT 'Latest Finish（预留）',
  `is_critical` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否关键路径',
  `resource_kind` varchar(16) DEFAULT NULL COMMENT '资源维度快照',
  `machine_type_id` int unsigned NOT NULL DEFAULT 0,
  `hr_department_id` int unsigned NOT NULL DEFAULT 0,
  `planned_minutes` decimal(14,2) NOT NULL DEFAULT 0 COMMENT '排程工时（分钟）',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_wo_op_plan` (`operation_id`),
  KEY `idx_wo_op_plan_preplan` (`preplan_id`),
  KEY `idx_wo_op_plan_wo` (`work_order_id`),
  KEY `idx_wo_op_plan_resource` (`resource_kind`,`machine_type_id`,`hr_department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作单工序排程结果';

CREATE TABLE IF NOT EXISTS `production_material_plan_detail` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `work_order_id` int unsigned NOT NULL,
  `operation_id` int unsigned DEFAULT NULL COMMENT '可选：关联工序，用于按工序分摊材料',
  `component_need_id` int unsigned DEFAULT NULL COMMENT '关联 production_component_need.id（逻辑外键）',
  `child_kind` varchar(16) NOT NULL COMMENT 'semi/material',
  `child_material_id` int unsigned NOT NULL DEFAULT 0,
  `required_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '理论需求量',
  `scrap_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '损耗/报废量',
  `net_required_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '净需求量',
  `stock_covered_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '库存覆盖量（重算后）',
  `shortage_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '最终缺口',
  `unit` varchar(16) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_mat_plan_preplan` (`preplan_id`),
  KEY `idx_mat_plan_wo` (`work_order_id`),
  KEY `idx_mat_plan_material` (`child_kind`,`child_material_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='材料测算明细（按工序与缺料分摊）';

CREATE TABLE IF NOT EXISTS `production_cost_plan_detail` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `work_order_id` int unsigned NOT NULL,
  `operation_id` int unsigned DEFAULT NULL,
  `cost_category` varchar(16) NOT NULL COMMENT 'material/labor/machine/overhead',
  `amount` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '成本金额',
  `currency` varchar(8) DEFAULT 'CNY',
  `unit_cost` decimal(18,6) DEFAULT NULL COMMENT '单位成本（可选）',
  `qty_basis` decimal(18,4) DEFAULT NULL COMMENT '成本计量数量（如工时/用量）',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_cost_plan_preplan` (`preplan_id`),
  KEY `idx_cost_plan_wo` (`work_order_id`),
  KEY `idx_cost_plan_cat` (`cost_category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成本测算分项明细';

