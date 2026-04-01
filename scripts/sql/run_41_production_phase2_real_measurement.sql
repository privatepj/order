
-- ----------------------------
-- 工序管理（模板 / 产品覆写 / 工作单工序快照）
-- ----------------------------
CREATE TABLE `production_process_template` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '模板名称',
  `version` varchar(32) NOT NULL DEFAULT 'v1' COMMENT '模板版本',
  `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_tpl_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工序模板头';

CREATE TABLE `production_process_template_step` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `template_id` int unsigned NOT NULL,
  `step_no` int unsigned NOT NULL DEFAULT 1 COMMENT '工序行号（从 1 开始，模板内唯一）',
  `step_code` varchar(64) DEFAULT NULL COMMENT '工序编码（可选）',
  `step_name` varchar(128) NOT NULL COMMENT '工序名称',
  `resource_kind` varchar(16) NOT NULL DEFAULT 'machine_type' COMMENT '资源维度：machine_type 或 hr_department',
  `machine_type_id` int unsigned NOT NULL DEFAULT 0 COMMENT '资源=machine_type 时使用',
  `hr_department_id` int unsigned NOT NULL DEFAULT 0 COMMENT '资源=hr_department 时使用',
  `setup_minutes` decimal(12,2) NOT NULL DEFAULT 0 COMMENT '准备/换型时间（分钟）',
  `run_minutes_per_unit` decimal(12,4) NOT NULL DEFAULT 0 COMMENT '单位运行时间（分钟/件）',
  `remark` varchar(255) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用该步骤',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tpl_step_no` (`template_id`,`step_no`),
  KEY `idx_tpl_step_tpl` (`template_id`),
  KEY `idx_tpl_step_resource` (`resource_kind`,`machine_type_id`,`hr_department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工序模板步骤';

CREATE TABLE `production_product_routing` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `product_id` int unsigned NOT NULL COMMENT '产品 product.id',
  `template_id` int unsigned NOT NULL COMMENT '绑定的工序模板 template.id',
  `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  `override_mode` varchar(16) NOT NULL DEFAULT 'inherit' COMMENT 'inherit=模板继承（覆写表可选）',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_prod_routing_product` (`product_id`),
  KEY `idx_prod_routing_template` (`template_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品工序路由（模板绑定/覆写）';

CREATE TABLE `production_product_routing_step` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `routing_id` int unsigned NOT NULL,
  `template_step_no` int unsigned NOT NULL COMMENT '被覆写的模板 step_no',
  `resource_kind_override` varchar(16) DEFAULT NULL COMMENT '可选覆写：资源维度',
  `machine_type_id_override` int unsigned NOT NULL DEFAULT 0 COMMENT '资源=machine_type 时使用',
  `hr_department_id_override` int unsigned NOT NULL DEFAULT 0 COMMENT '资源=hr_department 时使用',
  `setup_minutes_override` decimal(12,2) DEFAULT NULL COMMENT '准备时间覆写（分钟）',
  `run_minutes_per_unit_override` decimal(12,4) DEFAULT NULL COMMENT '单位运行时间覆写（分钟/件）',
  `step_name_override` varchar(128) DEFAULT NULL COMMENT '工序名称覆写',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_routing_step` (`routing_id`,`template_step_no`),
  KEY `idx_routing_step_routing` (`routing_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品路由工序覆写';

CREATE TABLE `production_work_order_operation` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `work_order_id` int unsigned NOT NULL,
  `step_no` int unsigned NOT NULL,
  `step_code` varchar(64) DEFAULT NULL,
  `step_name` varchar(128) NOT NULL,
  `resource_kind` varchar(16) DEFAULT NULL,
  `machine_type_id` int unsigned NOT NULL DEFAULT 0,
  `hr_department_id` int unsigned NOT NULL DEFAULT 0,
  `plan_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '用于计算的工序数量（快照）',
  `setup_minutes` decimal(12,2) NOT NULL DEFAULT 0 COMMENT '工序准备时间（快照）',
  `run_minutes_per_unit` decimal(12,4) NOT NULL DEFAULT 0 COMMENT '工序运行时间/单位（快照）',
  `estimated_setup_minutes` decimal(12,2) NOT NULL DEFAULT 0 COMMENT '预计准备时间',
  `estimated_run_minutes` decimal(12,2) NOT NULL DEFAULT 0 COMMENT '预计运行时间',
  `estimated_total_minutes` decimal(14,2) NOT NULL DEFAULT 0 COMMENT '预计总工时（分钟）',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_wo_op` (`work_order_id`,`step_no`),
  KEY `idx_wo_op_preplan` (`preplan_id`),
  KEY `idx_wo_op_wo` (`work_order_id`),
  KEY `idx_wo_op_seq` (`work_order_id`,`step_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作单工序快照';
