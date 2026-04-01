-- 工厂订单系统 - 全量建表脚本（新库部署用）
-- 使用前请先创建数据库: CREATE DATABASE IF NOT EXISTS sydixon_order DEFAULT CHARSET utf8mb4;
-- 新服务器部署只需执行本文件即可，无需再执行其他 SQL。
-- 本项目不在 MySQL 中创建任何 FOREIGN KEY / REFERENCES 约束；表间引用仅由列语义与应用层保证，
-- 与 ORM 中 primaryjoin/foreign()（非 db.ForeignKey）一致。新增表或迁移脚本禁止添加 CONSTRAINT ... FOREIGN KEY。

USE sydixon_order;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 角色表
-- ----------------------------
DROP TABLE IF EXISTS `role`;
CREATE TABLE `role` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(64) NOT NULL COMMENT '角色名称',
  `code` varchar(32) NOT NULL COMMENT '角色代码 admin/sales/warehouse/finance',
  `description` varchar(255) DEFAULT NULL,
  `allowed_menu_keys` json DEFAULT NULL COMMENT '可访问菜单 key 的 JSON 数组',
  `allowed_capability_keys` json DEFAULT NULL COMMENT '细项能力 key；NULL/[] 表示在已选菜单内默认全开',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色表';

-- ----------------------------
-- 用户表
-- ----------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(64) NOT NULL COMMENT '登录名',
  `password_hash` varchar(255) NOT NULL,
  `name` varchar(64) DEFAULT NULL COMMENT '姓名',
  `role_id` int unsigned NOT NULL,
  `requested_role_id` int unsigned DEFAULT NULL COMMENT '申请的目标角色',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  KEY `idx_role_id` (`role_id`),
  KEY `idx_requested_role_id` (`requested_role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- ----------------------------
-- 用户 API 令牌（OpenClaw 等）
-- ----------------------------
DROP TABLE IF EXISTS `user_api_token`;
CREATE TABLE `user_api_token` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `token_hash` char(64) NOT NULL COMMENT 'SHA256 十六进制',
  `label` varchar(128) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expires_at` datetime DEFAULT NULL,
  `revoked_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_token_hash` (`token_hash`),
  KEY `idx_user_api_token_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户 API 令牌';

-- ----------------------------
-- 经营主体（先删依赖客户的表）
-- ----------------------------
DROP TABLE IF EXISTS `customer_product`;
DROP TABLE IF EXISTS `customer`;
DROP TABLE IF EXISTS `company`;
CREATE TABLE `company` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '主体名称',
  `code` varchar(32) NOT NULL COMMENT '短码',
  `order_no_prefix` varchar(32) DEFAULT NULL COMMENT '订单号前缀',
  `delivery_no_prefix` varchar(32) DEFAULT NULL COMMENT '送货单号前缀',
  `billing_cycle_day` tinyint unsigned NOT NULL DEFAULT 1 COMMENT '转月日/月结日',
  `is_default` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否默认主体',
  `phone` varchar(32) DEFAULT NULL COMMENT '电话',
  `fax` varchar(32) DEFAULT NULL COMMENT '传真',
  `address` varchar(255) DEFAULT NULL COMMENT '地址',
  `contact_person` varchar(64) DEFAULT NULL COMMENT '联系人',
  `private_account` varchar(64) DEFAULT NULL COMMENT '对私账户',
  `public_account` varchar(64) DEFAULT NULL COMMENT '对公账户',
  `account_name` varchar(64) DEFAULT NULL COMMENT '户名',
  `bank_name` varchar(128) DEFAULT NULL COMMENT '开户行',
  `preparer_name` varchar(64) DEFAULT NULL COMMENT '对账制表人',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='经营主体';

INSERT INTO `company` (`name`, `code`, `order_no_prefix`, `delivery_no_prefix`, `billing_cycle_day`, `is_default`) VALUES
('经营主体A', 'A', 'A', 'A', 1, 1),
('经营主体B', 'B', 'B', 'B', 1, 0);

-- ----------------------------
-- 客户表
-- ----------------------------
CREATE TABLE `customer` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `customer_code` varchar(64) NOT NULL COMMENT '客户编码',
  `short_code` varchar(32) DEFAULT NULL COMMENT '客户简称',
  `name` varchar(128) NOT NULL COMMENT '客户名称',
  `contact` varchar(64) DEFAULT NULL,
  `phone` varchar(32) DEFAULT NULL,
  `fax` varchar(32) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `payment_terms` varchar(64) DEFAULT NULL COMMENT '结算方式',
  `remark` varchar(255) DEFAULT NULL,
  `company_id` int unsigned NOT NULL COMMENT '经营主体',
  `tax_point` decimal(6,4) DEFAULT NULL COMMENT '税率小数如0.13',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_customer_code` (`customer_code`),
  KEY `idx_company_id` (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户表';

-- ----------------------------
-- 产品主数据表
-- ----------------------------
DROP TABLE IF EXISTS `product`;
CREATE TABLE `product` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `product_code` varchar(64) NOT NULL COMMENT '内部物料编号',
  `name` varchar(128) NOT NULL COMMENT '产品名称',
  `spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `base_unit` varchar(16) DEFAULT NULL COMMENT '基础单位',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_product_code` (`product_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品主数据';

-- ----------------------------
-- 半成品/物料主数据表
-- ----------------------------
DROP TABLE IF EXISTS `semi_material`;
CREATE TABLE `semi_material` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `kind` varchar(16) NOT NULL COMMENT 'semi / material',
  `code` varchar(64) NOT NULL COMMENT '半成品/物料编号',
  `name` varchar(128) NOT NULL COMMENT '名称',
  `spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `base_unit` varchar(16) DEFAULT NULL COMMENT '基础单位',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_semi_material_code` (`code`),
  KEY `idx_semi_material_kind` (`kind`),
  KEY `idx_semi_material_spec` (`spec`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='半成品/物料主数据';

-- ----------------------------
-- BOM：父项/版本（bom_header）与子项用量（bom_line）
-- ----------------------------
DROP TABLE IF EXISTS `bom_line`;
DROP TABLE IF EXISTS `bom_header`;
CREATE TABLE `bom_header` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `parent_kind` varchar(16) NOT NULL COMMENT 'finished / semi / material',
  `parent_product_id` int unsigned NOT NULL DEFAULT 0 COMMENT '当 parent_kind=finished 时使用',
  `parent_material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '当 parent_kind IN(semi,material) 时使用',
  `version_no` int unsigned NOT NULL COMMENT '版本号（递增）',
  `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '0=历史版本 1=当前生效',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_bom_header_parent_version` (`parent_kind`,`parent_product_id`,`parent_material_id`,`version_no`),
  KEY `idx_bom_header_parent` (`parent_kind`,`parent_product_id`,`parent_material_id`),
  KEY `idx_bom_header_active` (`parent_kind`,`parent_product_id`,`parent_material_id`,`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='BOM 主表：父项/版本';

CREATE TABLE `bom_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `bom_header_id` int unsigned NOT NULL COMMENT '关联 bom_header.id（应用层保证）',
  `line_no` int unsigned NOT NULL COMMENT '行号（从 1 开始）',
  `child_kind` varchar(16) NOT NULL COMMENT 'semi / material',
  `child_material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '半成品/物料 id',
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL COMMENT '数量单位（用于展示）',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_bom_line_header_line` (`bom_header_id`,`line_no`),
  KEY `idx_bom_line_child` (`child_kind`,`child_material_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='BOM 明细：子项用量';

-- ----------------------------
-- 生产管理（预生产计划 / 工作单 / 缺料明细）
-- ----------------------------
-- 生产管理四张表：无外键约束；应用层保证 join 语义。
-- ----------------------------
DROP TABLE IF EXISTS `production_incident`;
DROP TABLE IF EXISTS `production_component_need`;
DROP TABLE IF EXISTS `production_work_order`;
DROP TABLE IF EXISTS `production_preplan_line`;
DROP TABLE IF EXISTS `production_preplan`;
DROP TABLE IF EXISTS `production_work_order_operation`;
DROP TABLE IF EXISTS `production_product_routing_step`;
DROP TABLE IF EXISTS `production_product_routing`;
DROP TABLE IF EXISTS `production_process_template_step`;
DROP TABLE IF EXISTS `production_process_template`;

CREATE TABLE `production_preplan` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `source_type` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual=手工预计划 order_shortage=由订单缺货生成 combined=合并测算',
  `plan_date` date NOT NULL COMMENT '预生产计划日期',
  `customer_id` int unsigned NOT NULL DEFAULT 0 COMMENT '关联 customer.id（可为空用 0 占位）',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/planned/closed',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_preplan_customer` (`customer_id`),
  KEY `idx_preplan_plan_date` (`plan_date`),
  KEY `idx_preplan_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预生产计划';

CREATE TABLE `production_preplan_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `line_no` int unsigned NOT NULL DEFAULT 1 COMMENT '行号（从 1 开始）',
  `source_type` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual=手工预计划 order_item=订单缺货生成',
  `source_order_item_id` int unsigned DEFAULT NULL,
  `product_id` int unsigned NOT NULL DEFAULT 0 COMMENT '成品 product.id',
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_preplan_line` (`preplan_id`,`line_no`),
  KEY `idx_preplan_line_preplan` (`preplan_id`),
  KEY `idx_preplan_line_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预生产计划明细（根需求）';

CREATE TABLE `production_work_order` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `root_preplan_line_id` int unsigned DEFAULT NULL COMMENT '追溯到根需求行（订单缺货行/预计划行）',
  `parent_kind` varchar(16) NOT NULL COMMENT 'finished=成品 semi=半成品 material=物料',
  `parent_product_id` int unsigned NOT NULL DEFAULT 0 COMMENT 'parent_kind=finished 时使用',
  `parent_material_id` int unsigned NOT NULL DEFAULT 0 COMMENT 'parent_kind IN(semi,material) 时使用',
  `plan_date` date NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'planned' COMMENT 'planned/released/closed/cancelled',
  `demand_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '根需求推导出的总需求',
  `stock_covered_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '库存覆盖数量（计算时点）',
  `to_produce_qty` decimal(18,4) NOT NULL DEFAULT 0 COMMENT '需要生产的净数量',
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `remark` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_work_order_preplan` (`preplan_id`),
  KEY `idx_work_order_root_line` (`root_preplan_line_id`),
  KEY `idx_work_order_parent` (`parent_kind`,`parent_product_id`,`parent_material_id`),
  KEY `idx_work_order_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生产工作单';

CREATE TABLE `production_component_need` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `preplan_id` int unsigned NOT NULL,
  `work_order_id` int unsigned NOT NULL,
  `root_preplan_line_id` int unsigned DEFAULT NULL COMMENT '追溯到根需求行',
  `bom_header_id` int unsigned DEFAULT NULL COMMENT '关联 bom_header.id（用于追溯）',
  `bom_line_id` int unsigned DEFAULT NULL COMMENT '关联 bom_line.id（用于追溯）',
  `child_kind` varchar(16) NOT NULL COMMENT 'semi/material',
  `child_material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '半成品/物料 id',
  `required_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `stock_covered_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `shortage_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `coverage_mode` varchar(16) NOT NULL DEFAULT 'stock' COMMENT 'stock=库存覆盖',
  `storage_area_hint` varchar(32) DEFAULT NULL COMMENT '未来：精确到仓储区的出入库提示',
  `unit` varchar(16) DEFAULT NULL COMMENT '用于展示',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_component_need_wo_bom_line` (`work_order_id`,`bom_line_id`),
  KEY `idx_component_need_preplan` (`preplan_id`),
  KEY `idx_component_need_wo` (`work_order_id`),
  KEY `idx_component_need_child` (`child_kind`,`child_material_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作单需求/缺料明细';

CREATE TABLE `production_incident` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `incident_no` varchar(32) DEFAULT NULL COMMENT '事故编号（唯一，可空后由系统补全）',
  `title` varchar(255) NOT NULL COMMENT '标题',
  `occurred_at` datetime NOT NULL COMMENT '发生时间',
  `workshop` varchar(128) DEFAULT NULL COMMENT '车间/地点',
  `severity` varchar(32) DEFAULT NULL COMMENT '严重程度',
  `status` varchar(16) NOT NULL DEFAULT 'open' COMMENT 'open/closed',
  `remark` varchar(500) DEFAULT NULL COMMENT '备注/D0 计划摘要',
  `d1_team` text COMMENT 'D1 小组',
  `d2_problem` text COMMENT 'D2 问题描述',
  `d3_containment` text COMMENT 'D3 临时措施',
  `d4_root_cause` text COMMENT 'D4 根本原因',
  `d5_corrective` text COMMENT 'D5 永久纠正措施',
  `d6_implementation` text COMMENT 'D6 实施与验证',
  `d7_prevention` text COMMENT 'D7 预防再发',
  `d8_recognition` text COMMENT 'D8 总结与表彰',
  `created_by` int unsigned NOT NULL COMMENT 'user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_production_incident_no` (`incident_no`),
  KEY `idx_production_incident_occurred` (`occurred_at`),
  KEY `idx_production_incident_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生产事故与 8D';

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

-- ----------------------------
-- 工序多层级与依赖关系（DAG）
-- ----------------------------
CREATE TABLE `production_process_node` (
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

CREATE TABLE `production_process_edge` (
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

CREATE TABLE `production_routing_node_override` (
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

-- ----------------------------
-- 测算结果：排程 / 材料分摊 / 成本
-- ----------------------------
CREATE TABLE `production_work_order_operation_plan` (
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

CREATE TABLE `production_material_plan_detail` (
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

CREATE TABLE `production_cost_plan_detail` (
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

-- ----------------------------
-- 客户产品表
-- ----------------------------
CREATE TABLE `customer_product` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `customer_id` int unsigned NOT NULL,
  `product_id` int unsigned NOT NULL,
  `customer_material_no` varchar(64) DEFAULT NULL COMMENT '客户料号',
  `material_no` varchar(64) DEFAULT NULL COMMENT '物料编号',
  `unit` varchar(16) DEFAULT NULL COMMENT '结算单位',
  `price` decimal(18,4) DEFAULT NULL COMMENT '单价',
  `currency` varchar(8) DEFAULT NULL COMMENT '币种',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_customer_id` (`customer_id`),
  KEY `idx_product_id` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户产品映射';

-- ----------------------------
-- 订单表头
-- ----------------------------
DROP TABLE IF EXISTS `order_item`;
DROP TABLE IF EXISTS `sales_order`;
CREATE TABLE `sales_order` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `order_no` varchar(64) NOT NULL COMMENT '我方订单编号',
  `customer_order_no` varchar(64) DEFAULT NULL COMMENT '客户订单编号',
  `customer_id` int unsigned NOT NULL,
  `salesperson` varchar(64) NOT NULL DEFAULT 'GaoMeiHua' COMMENT '销售人',
  `order_date` date DEFAULT NULL,
  `required_date` date DEFAULT NULL COMMENT '要求交货日',
  `status` varchar(32) NOT NULL DEFAULT 'pending' COMMENT 'pending/partial/delivered/closed',
  `payment_type` varchar(16) NOT NULL DEFAULT 'monthly' COMMENT 'monthly/cash/sample',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_no` (`order_no`),
  KEY `idx_customer_id` (`customer_id`),
  KEY `idx_customer_order_no` (`customer_order_no`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表头';

-- ----------------------------
-- 订单明细
-- ----------------------------
CREATE TABLE `order_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `order_id` int unsigned NOT NULL,
  `customer_product_id` int unsigned DEFAULT NULL COMMENT '来源客户产品表',
  `product_name` varchar(128) DEFAULT NULL COMMENT '品名',
  `product_spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `customer_material_no` varchar(64) DEFAULT NULL COMMENT '客户料号',
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `price` decimal(18,4) DEFAULT NULL,
  `amount` decimal(18,2) DEFAULT NULL COMMENT '该行总金额',
  `is_sample` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否样品',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_order_id` (`order_id`),
  KEY `idx_customer_product_id` (`customer_product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细';

-- ----------------------------
-- 快递公司
-- ----------------------------
DROP TABLE IF EXISTS `express_waybill`;
DROP TABLE IF EXISTS `delivery_item`;
DROP TABLE IF EXISTS `delivery`;
DROP TABLE IF EXISTS `express_company`;
CREATE TABLE `express_company` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '快递公司名称',
  `code` varchar(32) NOT NULL COMMENT '短码',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_express_company_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='快递公司';

INSERT INTO `express_company` (`name`, `code`, `is_active`) VALUES
('顺丰速运', 'SF', 1),
('其他快递', 'OTHER', 1);

-- ----------------------------
-- 送货单头
-- ----------------------------
CREATE TABLE `delivery` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `delivery_no` varchar(64) NOT NULL COMMENT '送货单号',
  `delivery_date` date NOT NULL,
  `customer_id` int unsigned NOT NULL,
  `express_company_id` int unsigned DEFAULT NULL COMMENT '快递公司；NULL 表示自配送',
  `express_waybill_id` int unsigned DEFAULT NULL COMMENT '占用的快递单号行',
  `waybill_no` varchar(64) DEFAULT NULL COMMENT '快递单号',
  `status` varchar(32) NOT NULL DEFAULT 'created' COMMENT 'created/shipped/signed',
  `driver` varchar(64) DEFAULT NULL,
  `plate_no` varchar(32) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_delivery_no` (`delivery_no`),
  KEY `idx_customer_id` (`customer_id`),
  KEY `idx_delivery_date` (`delivery_date`),
  KEY `idx_express_company_id` (`express_company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='送货单头';

-- ----------------------------
-- 快递单号池
-- ----------------------------
CREATE TABLE `express_waybill` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `express_company_id` int unsigned NOT NULL,
  `waybill_no` varchar(64) NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'available' COMMENT 'available/used',
  `delivery_id` int unsigned DEFAULT NULL,
  `used_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_company_waybill` (`express_company_id`, `waybill_no`),
  KEY `idx_available` (`express_company_id`, `status`, `id`),
  KEY `idx_delivery_id` (`delivery_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='快递单号池';

-- ----------------------------
-- 送货明细
-- ----------------------------
CREATE TABLE `delivery_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `delivery_id` int unsigned NOT NULL,
  `order_item_id` int unsigned NOT NULL,
  `order_id` int unsigned NOT NULL COMMENT '冗余便于汇总',
  `product_name` varchar(128) DEFAULT NULL,
  `customer_material_no` varchar(64) DEFAULT NULL,
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_delivery_id` (`delivery_id`),
  KEY `idx_order_item_id` (`order_item_id`),
  KEY `idx_order_id` (`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='送货明细';

-- ----------------------------
-- 每日库存录入（单仓快照；多仓可后续加 warehouse 表与 warehouse_id）
-- ----------------------------
DROP TABLE IF EXISTS `inventory_daily_line`;
DROP TABLE IF EXISTS `inventory_daily_record`;
CREATE TABLE `inventory_daily_record` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `record_date` date NOT NULL COMMENT '业务日',
  `status` varchar(16) NOT NULL DEFAULT 'confirmed' COMMENT 'draft=草稿 confirmed=已确认',
  `remark` varchar(500) DEFAULT NULL,
  `created_by` int unsigned NOT NULL COMMENT '录入人 user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_inv_daily_record_date` (`record_date`),
  KEY `idx_inv_daily_created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日库存录入主表';

CREATE TABLE `inventory_daily_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `header_id` int unsigned NOT NULL,
  `product_id` int unsigned NOT NULL,
  `quantity` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `note` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inv_daily_header_product` (`header_id`,`product_id`),
  KEY `idx_inv_daily_line_header` (`header_id`),
  KEY `idx_inv_daily_line_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日库存明细';

-- ----------------------------
-- 期初结存 + 进出明细台账（与 Excel 主表逻辑一致；收发由明细汇总）
-- ----------------------------
DROP TABLE IF EXISTS `inventory_movement`;
DROP TABLE IF EXISTS `inventory_movement_batch`;
DROP TABLE IF EXISTS `inventory_opening_balance`;
CREATE TABLE `inventory_opening_balance` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL COMMENT 'finished=成品 semi=半成品',
  `product_id` int unsigned NOT NULL DEFAULT 0 COMMENT '成品时关联 product.id，0=无',
  `material_id` int unsigned NOT NULL DEFAULT 0 COMMENT '半成品预留，0=无',
  `storage_area` varchar(32) NOT NULL DEFAULT '' COMMENT '仓储区',
  `opening_qty` decimal(18,4) NOT NULL DEFAULT 0,
  `unit` varchar(16) DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inv_opening_bucket` (`category`,`product_id`,`material_id`,`storage_area`),
  KEY `idx_inv_opening_product` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存期初结存';

CREATE TABLE `inventory_movement_batch` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL COMMENT 'finished / semi',
  `biz_date` date NOT NULL COMMENT '业务日期',
  `direction` varchar(8) NOT NULL COMMENT 'in=入库 out=出库',
  `source` varchar(16) NOT NULL COMMENT 'form=手工 excel=导入 delivery=送货出库',
  `line_count` int unsigned NOT NULL DEFAULT 0 COMMENT '明细行数',
  `original_filename` varchar(255) DEFAULT NULL COMMENT 'Excel 导入时的文件名',
  `source_delivery_id` int unsigned DEFAULT NULL COMMENT '送货批次时关联 delivery.id',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inv_mov_batch_delivery` (`source_delivery_id`),
  KEY `idx_inv_mov_batch_biz_date` (`biz_date`),
  KEY `idx_inv_mov_batch_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存进出批次（手工/导入/送货）';

CREATE TABLE `inventory_movement` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `category` varchar(16) NOT NULL COMMENT 'finished / semi',
  `direction` varchar(8) NOT NULL COMMENT 'in=入库 out=出库',
  `product_id` int unsigned NOT NULL DEFAULT 0,
  `material_id` int unsigned NOT NULL DEFAULT 0,
  `storage_area` varchar(32) NOT NULL DEFAULT '',
  `quantity` decimal(18,4) NOT NULL,
  `unit` varchar(16) DEFAULT NULL,
  `biz_date` date NOT NULL COMMENT '业务日期',
  `source_type` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual / delivery',
  `source_delivery_id` int unsigned DEFAULT NULL,
  `source_delivery_item_id` int unsigned DEFAULT NULL,
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `movement_batch_id` int unsigned DEFAULT NULL COMMENT '关联 inventory_movement_batch.id',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_inv_mov_delivery_item` (`source_delivery_item_id`),
  KEY `idx_inv_mov_delivery` (`source_delivery_id`),
  KEY `idx_inv_mov_product_area` (`product_id`,`storage_area`),
  KEY `idx_inv_mov_biz_date` (`biz_date`),
  KEY `idx_inv_mov_batch` (`movement_batch_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='库存进出明细';

-- ----------------------------
-- 接口审计日志
-- ----------------------------
DROP TABLE IF EXISTS `audit_log`;
CREATE TABLE `audit_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `event_type` varchar(16) NOT NULL,
  `method` varchar(8) DEFAULT NULL,
  `path` varchar(512) NOT NULL,
  `query_string` varchar(2048) DEFAULT NULL,
  `status_code` smallint DEFAULT NULL,
  `duration_ms` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `auth_type` varchar(16) NOT NULL,
  `ip` varchar(45) NOT NULL,
  `user_agent` varchar(512) DEFAULT NULL,
  `endpoint` varchar(128) DEFAULT NULL,
  `extra` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_audit_log_created_at` (`created_at`),
  KEY `ix_audit_log_user_created` (`user_id`, `created_at`),
  KEY `ix_audit_log_path` (`path`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- 人力资源（部门 / 人员 / 工资 / 绩效；逻辑关联 company / user；无 DB 外键）
-- ----------------------------
DROP TABLE IF EXISTS `hr_performance_review`;
DROP TABLE IF EXISTS `hr_payroll_line`;
DROP TABLE IF EXISTS `hr_employee`;
DROP TABLE IF EXISTS `hr_department`;
CREATE TABLE `hr_department` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `name` varchar(128) NOT NULL COMMENT '部门名称',
  `sort_order` int NOT NULL DEFAULT 0,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hr_dept_company_name` (`company_id`,`name`),
  KEY `idx_hr_dept_company` (`company_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HR 部门';

CREATE TABLE `hr_employee` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `department_id` int unsigned DEFAULT NULL COMMENT 'hr_department.id',
  `user_id` int unsigned DEFAULT NULL COMMENT '可选关联登录用户 user.id',
  `employee_no` varchar(32) NOT NULL COMMENT '工号',
  `name` varchar(64) NOT NULL,
  `id_card` varchar(32) DEFAULT NULL COMMENT '身份证（敏感）',
  `phone` varchar(32) DEFAULT NULL,
  `job_title` varchar(64) DEFAULT NULL COMMENT '岗位',
  `status` varchar(16) NOT NULL DEFAULT 'active' COMMENT 'active=在职 left=离职',
  `hire_date` date DEFAULT NULL,
  `leave_date` date DEFAULT NULL,
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hr_emp_company_no` (`company_id`,`employee_no`),
  KEY `idx_hr_emp_company` (`company_id`),
  KEY `idx_hr_emp_dept` (`department_id`),
  KEY `idx_hr_emp_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HR 人员档案';

CREATE TABLE `hr_payroll_line` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL COMMENT 'hr_employee.id',
  `period` char(7) NOT NULL COMMENT '账期 YYYY-MM',
  `base_salary` decimal(14,2) NOT NULL DEFAULT 0.00,
  `allowance` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '津贴',
  `deduction` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '扣款',
  `net_pay` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '实发',
  `remark` varchar(500) DEFAULT NULL,
  `created_by` int unsigned NOT NULL COMMENT 'user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hr_pay_company_emp_period` (`company_id`,`employee_id`,`period`),
  KEY `idx_hr_pay_company_period` (`company_id`,`period`),
  KEY `idx_hr_pay_employee` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HR 工资明细（按月一行）';

CREATE TABLE `hr_performance_review` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `cycle` varchar(32) NOT NULL COMMENT '考核周期 如 2026-Q1',
  `score` decimal(6,2) DEFAULT NULL,
  `comment` text COMMENT '评语',
  `reviewer_user_id` int unsigned DEFAULT NULL COMMENT '考核人 user.id',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft=草稿 finalized=已定稿',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_hr_perf_company_emp_cycle` (`company_id`,`employee_id`,`cycle`),
  KEY `idx_hr_perf_company` (`company_id`),
  KEY `idx_hr_perf_employee` (`employee_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HR 绩效考核';

-- ----------------------------
-- 机台管理（机台种类 / 机台台账 / 运转情况；逻辑关联 user；无 DB 外键）
-- ----------------------------
DROP TABLE IF EXISTS `machine_runtime_log`;
DROP TABLE IF EXISTS `machine`;
DROP TABLE IF EXISTS `machine_type`;
CREATE TABLE `machine_type` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `code` varchar(32) NOT NULL COMMENT '机台种类编码',
  `name` varchar(64) NOT NULL COMMENT '机台种类名称',
  `is_active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '1=启用 0=停用',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_machine_type_code` (`code`),
  UNIQUE KEY `uk_machine_type_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台种类';

CREATE TABLE `machine` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `machine_no` varchar(32) NOT NULL COMMENT '机台编号',
  `name` varchar(64) NOT NULL COMMENT '机台名称',
  `machine_type_id` int unsigned NOT NULL COMMENT '机台种类 machine_type.id',
  `capacity_per_hour` decimal(12,2) NOT NULL DEFAULT 0.00 COMMENT '标准产能（件/小时）',
  `status` varchar(16) NOT NULL DEFAULT 'enabled' COMMENT 'enabled/disabled/maintenance/scrapped',
  `location` varchar(128) DEFAULT NULL COMMENT '车间/产线',
  `owner_user_id` int unsigned DEFAULT NULL COMMENT '责任人 user.id',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_machine_no` (`machine_no`),
  KEY `idx_machine_type` (`machine_type_id`),
  KEY `idx_machine_status` (`status`),
  KEY `idx_machine_owner` (`owner_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台台账';

CREATE TABLE `machine_runtime_log` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `machine_id` int unsigned NOT NULL COMMENT '机台 machine.id',
  `runtime_status` varchar(16) NOT NULL COMMENT 'running/idle/fault',
  `started_at` datetime NOT NULL COMMENT '开始时间',
  `ended_at` datetime DEFAULT NULL COMMENT '结束时间，NULL=进行中',
  `remark` varchar(255) DEFAULT NULL,
  `created_by` int unsigned NOT NULL COMMENT '录入人 user.id',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_machine_runtime_machine` (`machine_id`),
  KEY `idx_machine_runtime_started` (`started_at`),
  KEY `idx_machine_runtime_open` (`machine_id`,`ended_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='机台运转情况记录';

-- ----------------------------
-- 采购管理（请购 / 采购单 / 收货 / 入库；逻辑关联 company / user；无 DB 外键）
-- ----------------------------
DROP TABLE IF EXISTS `purchase_stock_in`;
DROP TABLE IF EXISTS `purchase_receipt`;
DROP TABLE IF EXISTS `purchase_order`;
DROP TABLE IF EXISTS `purchase_requisition`;
CREATE TABLE `purchase_requisition` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `req_no` varchar(32) NOT NULL COMMENT '请购单号',
  `requester_user_id` int unsigned NOT NULL COMMENT '申请人 user.id',
  `supplier_name` varchar(128) NOT NULL COMMENT '供应商',
  `item_name` varchar(128) NOT NULL COMMENT '物料名称',
  `item_spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `qty` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '请购数量',
  `unit` varchar(16) NOT NULL DEFAULT 'pcs' COMMENT '单位',
  `expected_date` date DEFAULT NULL COMMENT '期望到货日期',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/ordered/cancelled',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_requisition_no` (`req_no`),
  KEY `idx_purchase_requisition_company` (`company_id`),
  KEY `idx_purchase_requisition_requester` (`requester_user_id`),
  KEY `idx_purchase_requisition_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购请购单';

CREATE TABLE `purchase_order` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `po_no` varchar(32) NOT NULL COMMENT '采购单号',
  `requisition_id` int unsigned DEFAULT NULL COMMENT '请购单 purchase_requisition.id',
  `buyer_user_id` int unsigned NOT NULL COMMENT '采购员 user.id',
  `supplier_name` varchar(128) NOT NULL COMMENT '供应商',
  `item_name` varchar(128) NOT NULL COMMENT '物料名称',
  `item_spec` varchar(128) DEFAULT NULL COMMENT '规格',
  `qty` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '采购数量',
  `unit` varchar(16) NOT NULL DEFAULT 'pcs' COMMENT '单位',
  `unit_price` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '单价',
  `amount` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '金额',
  `expected_date` date DEFAULT NULL COMMENT '期望到货日期',
  `status` varchar(24) NOT NULL DEFAULT 'draft' COMMENT 'draft/ordered/partially_received/received/cancelled',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_order_no` (`po_no`),
  KEY `idx_purchase_order_company` (`company_id`),
  KEY `idx_purchase_order_req` (`requisition_id`),
  KEY `idx_purchase_order_buyer` (`buyer_user_id`),
  KEY `idx_purchase_order_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购单';

CREATE TABLE `purchase_receipt` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `receipt_no` varchar(32) NOT NULL COMMENT '收货单号',
  `purchase_order_id` int unsigned NOT NULL COMMENT '采购单 purchase_order.id',
  `receiver_user_id` int unsigned NOT NULL COMMENT '收货人 user.id',
  `received_qty` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '收货数量',
  `received_at` datetime NOT NULL COMMENT '收货时间',
  `status` varchar(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/posted',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_receipt_no` (`receipt_no`),
  KEY `idx_purchase_receipt_company` (`company_id`),
  KEY `idx_purchase_receipt_po` (`purchase_order_id`),
  KEY `idx_purchase_receipt_receiver` (`receiver_user_id`),
  KEY `idx_purchase_receipt_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购收货单';

CREATE TABLE `purchase_stock_in` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `company_id` int unsigned NOT NULL COMMENT '经营主体 company.id',
  `stock_in_no` varchar(32) NOT NULL COMMENT '入库单号',
  `receipt_id` int unsigned NOT NULL COMMENT '收货单 purchase_receipt.id',
  `qty` decimal(14,2) NOT NULL DEFAULT 0.00 COMMENT '入库数量',
  `storage_area` varchar(64) DEFAULT NULL COMMENT '仓储区',
  `stock_in_at` datetime NOT NULL COMMENT '入库时间',
  `created_by` int unsigned NOT NULL COMMENT '创建人 user.id',
  `remark` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_purchase_stock_in_no` (`stock_in_no`),
  KEY `idx_purchase_stock_in_company` (`company_id`),
  KEY `idx_purchase_stock_in_receipt` (`receipt_id`),
  KEY `idx_purchase_stock_in_creator` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购入库记录';

-- ----------------------------
-- 导航与细项能力（RBAC 库表，与 run_15/run_16 一致）
-- ----------------------------
DROP TABLE IF EXISTS `role_allowed_capability`;
DROP TABLE IF EXISTS `role_allowed_nav`;
DROP TABLE IF EXISTS `sys_capability`;
DROP TABLE IF EXISTS `sys_nav_item`;

CREATE TABLE `sys_nav_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `parent_id` int unsigned DEFAULT NULL,
  `code` varchar(64) NOT NULL,
  `title` varchar(128) NOT NULL,
  `endpoint` varchar(128) DEFAULT NULL COMMENT 'Flask endpoint，如 main.order_list',
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `admin_only` tinyint(1) NOT NULL DEFAULT 0 COMMENT '仅 admin 角色可分配',
  `is_assignable` tinyint(1) NOT NULL DEFAULT 1 COMMENT '0=仅导航分组节点',
  `landing_priority` int DEFAULT NULL COMMENT '越小越优先作为登录落地页',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_nav_code` (`code`),
  KEY `idx_nav_parent` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='导航菜单项';

CREATE TABLE `sys_capability` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `code` varchar(128) NOT NULL,
  `title` varchar(255) NOT NULL,
  `nav_item_code` varchar(64) NOT NULL COMMENT '归属菜单叶子 code',
  `group_label` varchar(128) NOT NULL DEFAULT '',
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cap_code` (`code`),
  KEY `idx_cap_nav` (`nav_item_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='细项能力';

CREATE TABLE `role_allowed_nav` (
  `role_id` int unsigned NOT NULL,
  `nav_code` varchar(64) NOT NULL,
  PRIMARY KEY (`role_id`, `nav_code`),
  KEY `idx_ran_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色可访问菜单';

CREATE TABLE `role_allowed_capability` (
  `role_id` int unsigned NOT NULL,
  `cap_code` varchar(128) NOT NULL,
  PRIMARY KEY (`role_id`, `cap_code`),
  KEY `idx_rac_role` (`role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色显式细项能力白名单';

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- 初始数据：角色
-- ----------------------------
INSERT INTO `role` (`name`, `code`, `description`, `allowed_menu_keys`) VALUES
('管理员', 'admin', '系统管理员', NULL),
('销售', 'sales', '销售员', CAST('["order","delivery","customer","product","customer_product","reconciliation"]' AS JSON)),
('仓管', 'warehouse', '仓管员', CAST('["order","delivery","express","inventory_query","inventory_ops","customer","product","semi_material","bom","production_preplan","production_incident","production_process","machine_type","machine_asset","machine_runtime","procurement_requisition","procurement_order","procurement_receipt","procurement_stockin","customer_product","reconciliation"]' AS JSON)),
('财务', 'finance', '财务人员', CAST('["order","delivery","customer","product","customer_product","reconciliation"]' AS JSON)),
('待分配', 'pending', '注册后等待管理员分配', CAST('[]' AS JSON));

-- ----------------------------
-- 初始数据：管理员用户 (默认密码 password，请首次登录后修改)
-- ----------------------------
INSERT INTO `user` (`username`, `password_hash`, `name`, `role_id`, `is_active`) VALUES
('admin', 'password', '管理员', 1, 1);

-- ----------------------------
-- 初始数据：导航树与能力定义（run_16 为旧库种子基线；此处另含 run_18 / run_20 / run_21 等补丁中的能力键，供新库一次到位）
-- ----------------------------
INSERT INTO `sys_nav_item` (`id`, `parent_id`, `code`, `title`, `endpoint`, `sort_order`, `is_active`, `admin_only`, `is_assignable`, `landing_priority`) VALUES
(1, NULL, 'order', '订单', 'main.order_list', 10, 1, 0, 1, 10),
(2, NULL, 'nav_warehouse', '仓管', NULL, 20, 1, 0, 0, NULL),
(3, 2, 'delivery', '送货', 'main.delivery_list', 10, 1, 0, 1, 20),
(4, 2, 'express', '快递', 'main.express_company_list', 20, 1, 0, 1, 80),
(5, 2, 'inventory_query', '库存查询', 'main.inventory_stock_query', 30, 1, 0, 1, 85),
(6, 2, 'inventory_ops', '库存录入', 'main.inventory_list', 40, 1, 0, 1, 86),
(21, NULL, 'production', '生产管理', NULL, 15, 1, 0, 0, NULL),
(36, 21, 'production_preplan', '预生产计划', 'main.production_preplan_list', 10, 1, 0, 1, 87),
(37, 21, 'production_incident', '生产事故', 'main.production_incident_list', 20, 1, 0, 1, 88),
(38, 21, 'production_process', '工序管理', 'main.production_process_template_list', 30, 1, 0, 1, 89),
(22, NULL, 'nav_hr', '人力资源', NULL, 17, 1, 0, 0, NULL),
(23, 22, 'hr_department', '部门', 'main.hr_department_list', 10, 1, 0, 1, 92),
(24, 22, 'hr_employee', '人员档案', 'main.hr_employee_list', 20, 1, 0, 1, 93),
(25, 22, 'hr_payroll', '工资录入', 'main.hr_payroll_list', 30, 1, 0, 1, 94),
(26, 22, 'hr_performance', '绩效管理', 'main.hr_performance_list', 40, 1, 0, 1, 95),
(27, NULL, 'nav_machine', '机台管理', NULL, 16, 1, 0, 0, NULL),
(28, 27, 'machine_type', '机台种类', 'main.machine_type_list', 10, 1, 0, 1, 96),
(29, 27, 'machine_asset', '机台台账', 'main.machine_list', 20, 1, 0, 1, 97),
(30, 27, 'machine_runtime', '运转情况', 'main.machine_runtime_list', 30, 1, 0, 1, 98),
(31, NULL, 'nav_procurement', '采购管理', NULL, 18, 1, 0, 0, NULL),
(32, 31, 'procurement_requisition', '采购请购', 'main.procurement_requisition_list', 10, 1, 0, 1, 102),
(33, 31, 'procurement_order', '采购单', 'main.procurement_order_list', 20, 1, 0, 1, 103),
(34, 31, 'procurement_receipt', '采购收货', 'main.procurement_receipt_list', 30, 1, 0, 1, 104),
(35, 31, 'procurement_stockin', '采购入库', 'main.procurement_stockin_list', 40, 1, 0, 1, 105),
(7, NULL, 'nav_base', '基础数据', NULL, 30, 1, 0, 0, NULL),
(8, 7, 'customer', '客户', 'main.customer_list', 10, 1, 0, 1, 30),
(9, 7, 'product', '产品', 'main.product_list', 20, 1, 0, 1, 40),
(10, 7, 'customer_product', '客户产品', 'main.customer_product_list', 30, 1, 0, 1, 50),
(11, 7, 'company', '公司主体', 'main.company_list', 40, 1, 1, 1, 90),
(12, 7, 'user_mgmt', '用户管理', 'main.user_list', 50, 1, 1, 1, 100),
(13, 7, 'role_mgmt', '角色管理', 'main.role_list', 60, 1, 1, 1, 101),
(19, 7, 'semi_material', '半成品/物料', 'main.semi_material_list', 25, 1, 0, 1, 88),
(20, 7, 'bom', 'BOM 管理', 'main.bom_list', 26, 1, 0, 1, 89),
(14, NULL, 'nav_finance', '财务', NULL, 40, 1, 0, 0, NULL),
(15, 14, 'reconciliation', '对账导出', 'main.reconciliation_export', 10, 1, 0, 1, 60),
(16, NULL, 'nav_report', '报表导出', NULL, 50, 1, 0, 0, NULL),
(17, 16, 'report_notes', '导出送货单Excel', 'main.report_export_delivery_notes', 10, 1, 0, 1, 70),
(18, 16, 'report_records', '导出送货记录Excel', 'main.report_export_delivery_records', 20, 1, 0, 1, 71);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('order.filter.customer', '订单列表：按客户筛选', 'order', '订单', 10),
('order.filter.status', '订单列表：按状态筛选', 'order', '订单', 20),
('order.filter.payment_type', '订单列表：按付款类型筛选', 'order', '订单', 30),
('order.filter.keyword', '订单列表：关键词搜索', 'order', '订单', 40),
('order.action.create', '订单：新建', 'order', '订单', 50),
('order.action.edit', '订单：编辑', 'order', '订单', 60),
('order.action.delete', '订单：删除', 'order', '订单', 70),
('customer_product.filter.customer', '客户产品列表：按客户筛选', 'customer_product', '客户产品', 10),
('customer_product.filter.keyword', '客户产品列表：关键词搜索', 'customer_product', '客户产品', 20),
('customer_product.action.create', '客户产品：新建', 'customer_product', '客户产品', 30),
('customer_product.action.edit', '客户产品：编辑', 'customer_product', '客户产品', 40),
('customer_product.action.delete', '客户产品：删除', 'customer_product', '客户产品', 50),
('customer_product.action.import', '客户产品：Excel 导入', 'customer_product', '客户产品', 60),
('customer_product.action.export_template', '客户产品：下载导入模板', 'customer_product', '客户产品', 70),
('delivery.filter.customer', '送货列表：按客户筛选', 'delivery', '送货', 10),
('delivery.filter.status', '送货列表：按状态筛选', 'delivery', '送货', 20),
('delivery.filter.keyword', '送货列表：关键词搜索', 'delivery', '送货', 30),
('delivery.action.create', '送货：新建送货单', 'delivery', '送货', 40),
('delivery.action.detail', '送货：详情', 'delivery', '送货', 50),
('delivery.action.print', '送货：打印', 'delivery', '送货', 60),
('delivery.action.mark_shipped', '送货：标记已发', 'delivery', '送货', 70),
('delivery.action.mark_created', '送货：标记待发', 'delivery', '送货', 80),
('delivery.action.mark_expired', '送货：标记失效', 'delivery', '送货', 90),
('delivery.action.delete', '送货：删除', 'delivery', '送货', 100),
('delivery.action.clear_waybill', '送货：清空快递单号', 'delivery', '送货', 110),
('delivery.action.edit_delivery_no', '送货：修改送货单号（列表）', 'delivery', '送货', 115),
('delivery.action.edit_waybill', '送货：修改快递单号（列表）', 'delivery', '送货', 116),
('delivery.api.customers_search', '送货：客户搜索接口', 'delivery', '送货', 120),
('delivery.api.pending_items', '送货：待送明细接口', 'delivery', '送货', 130),
('delivery.api.next_waybill', '送货：取单号接口', 'delivery', '送货', 140),
('report_notes.page.view', '报表：送货单导出页', 'report_notes', '报表导出', 10),
('report_notes.export.run', '报表：执行导出送货单', 'report_notes', '报表导出', 20),
('report_records.page.view', '报表：送货记录导出页', 'report_records', '报表导出', 10),
('report_records.export.run', '报表：执行导出送货记录', 'report_records', '报表导出', 20),
('express.action.company_create', '快递：新建快递公司', 'express', '快递', 10),
('express.action.company_edit', '快递：编辑快递公司', 'express', '快递', 20),
('express.action.waybill_import', '快递：单号池导入', 'express', '快递', 30),
('inventory_query.filter.category', '库存查询：类别', 'inventory_query', '库存查询', 10),
('inventory_query.filter.spec', '库存查询：规格', 'inventory_query', '库存查询', 20),
('inventory_query.filter.name_spec', '库存查询：品名/规格/编号', 'inventory_query', '库存查询', 30),
('inventory_query.filter.storage_area', '库存查询：仓储区', 'inventory_query', '库存查询', 40),
('inventory_ops.api.products_search', '库存录入：产品搜索接口', 'inventory_ops', '库存录入', 10),
('inventory_ops.api.suggest_storage_area', '库存录入：仓储区建议接口', 'inventory_ops', '库存录入', 20),
('inventory_ops.movement.list', '库存录入：库存批次列表', 'inventory_ops', '库存录入', 25),
('inventory_ops.movement.create', '库存录入：手工出入库', 'inventory_ops', '库存录入', 30),
('inventory_ops.movement.delete', '库存录入：删除进出明细', 'inventory_ops', '库存录入', 40),
('inventory_ops.movement_batch.void', '库存录入：撤销手工/导入批次', 'inventory_ops', '库存录入', 45),
('inventory_ops.opening.list', '库存录入：期初列表', 'inventory_ops', '库存录入', 50),
('inventory_ops.opening.create', '库存录入：新建期初', 'inventory_ops', '库存录入', 60),
('inventory_ops.opening.edit', '库存录入：编辑期初', 'inventory_ops', '库存录入', 70),
('inventory_ops.opening.delete', '库存录入：删除期初', 'inventory_ops', '库存录入', 80),
('inventory_ops.daily.list', '库存录入：日结列表', 'inventory_ops', '库存录入', 90),
('inventory_ops.daily.create', '库存录入：新建日结', 'inventory_ops', '库存录入', 100),
('inventory_ops.daily.detail', '库存录入：日结详情', 'inventory_ops', '库存录入', 110),
('inventory_ops.daily.edit', '库存录入：编辑日结', 'inventory_ops', '库存录入', 120),
('inventory_ops.daily.delete', '库存录入：删除日结', 'inventory_ops', '库存录入', 130),
('customer.filter.keyword', '客户列表：关键词搜索', 'customer', '客户', 10),
('customer.action.create', '客户：新建', 'customer', '客户', 20),
('customer.action.edit', '客户：编辑', 'customer', '客户', 30),
('customer.action.delete', '客户：删除', 'customer', '客户', 40),
('customer.action.import', '客户：Excel 导入', 'customer', '客户', 50),
('product.filter.keyword', '产品列表：关键词搜索', 'product', '产品', 10),
('product.action.create', '产品：新建', 'product', '产品', 20),
('product.action.edit', '产品：编辑', 'product', '产品', 30),
('product.action.delete', '产品：删除', 'product', '产品', 40),
('product.action.import', '产品：Excel 导入', 'product', '产品', 50),
-- 半成品/物料主数据
('semi_material.filter.keyword', '半成品/物料列表：关键词搜索', 'semi_material', '半成品/物料', 10),
('semi_material.action.create', '半成品/物料：新建主数据', 'semi_material', '半成品/物料', 20),
('semi_material.action.edit', '半成品/物料：编辑主数据', 'semi_material', '半成品/物料', 30),
('semi_material.action.delete', '半成品/物料：删除主数据', 'semi_material', '半成品/物料', 40),
('semi_material.action.import', '半成品/物料：Excel 导入', 'semi_material', '半成品/物料', 50),
-- BOM 主数据
('bom.filter.keyword', 'BOM 列表：关键词搜索', 'bom', 'BOM', 10),
('bom.action.create', 'BOM：新建', 'bom', 'BOM', 20),
('bom.action.edit', 'BOM：编辑', 'bom', 'BOM', 30),
('bom.action.delete', 'BOM：删除', 'bom', 'BOM', 40),
('bom.action.import', 'BOM：Excel 导入', 'bom', 'BOM', 50),
-- 预生产计划 / 生产事故
('production.preplan.action.create', '预生产计划：新建', 'production_preplan', '预生产计划', 10),
('production.preplan.action.edit', '预生产计划：编辑', 'production_preplan', '预生产计划', 20),
('production.preplan.action.delete', '预生产计划：删除', 'production_preplan', '预生产计划', 30),
('production.calc.action.run', '预生产计划：生产测算运行', 'production_preplan', '预生产计划', 40),
('production_incident.filter.keyword', '生产事故：关键词筛选', 'production_incident', '生产事故', 11),
('production_incident.action.create', '生产事故：新建', 'production_incident', '生产事故', 21),
('production_incident.action.edit', '生产事故：编辑', 'production_incident', '生产事故', 31),
('production_incident.action.delete', '生产事故：删除', 'production_incident', '生产事故', 41),
('production_incident.report.8d', '生产事故：8D 报告（打印/导出）', 'production_incident', '生产事故', 51),
('hr_department.filter.keyword', 'HR 部门：关键词', 'hr_department', '人力资源', 200),
('hr_department.action.create', 'HR 部门：新建', 'hr_department', '人力资源', 210),
('hr_department.action.edit', 'HR 部门：编辑', 'hr_department', '人力资源', 220),
('hr_department.action.delete', 'HR 部门：删除', 'hr_department', '人力资源', 230),
('hr_employee.filter.company', 'HR 人员：按主体筛选', 'hr_employee', '人力资源', 300),
('hr_employee.filter.keyword', 'HR 人员：关键词', 'hr_employee', '人力资源', 310),
('hr_employee.action.create', 'HR 人员：新建', 'hr_employee', '人力资源', 320),
('hr_employee.action.edit', 'HR 人员：编辑', 'hr_employee', '人力资源', 330),
('hr_employee.action.delete', 'HR 人员：删除', 'hr_employee', '人力资源', 340),
('hr_employee.action.import', 'HR 人员：Excel 导入', 'hr_employee', '人力资源', 350),
('hr_employee.action.export_template', 'HR 人员：下载导入模板', 'hr_employee', '人力资源', 360),
('hr_employee.view_sensitive', 'HR 人员：查看身份证/完整手机', 'hr_employee', '人力资源', 370),
('hr_payroll.view', 'HR 工资：查看', 'hr_payroll', '人力资源', 400),
('hr_payroll.edit', 'HR 工资：录入与修改', 'hr_payroll', '人力资源', 410),
('hr_payroll.export', 'HR 工资：导出 Excel', 'hr_payroll', '人力资源', 420),
('hr_performance.action.create', 'HR 绩效：新建', 'hr_performance', '人力资源', 500),
('hr_performance.action.edit', 'HR 绩效：编辑', 'hr_performance', '人力资源', 510),
('hr_performance.action.delete', 'HR 绩效：删除', 'hr_performance', '人力资源', 520),
('hr_performance.action.finalize', 'HR 绩效：定稿', 'hr_performance', '人力资源', 530),
('hr_performance.action.override', 'HR 绩效：已定稿后修改', 'hr_performance', '人力资源', 540),
('machine_type.action.create', '机台种类：新建', 'machine_type', '机台管理', 600),
('machine_type.action.edit', '机台种类：编辑', 'machine_type', '机台管理', 610),
('machine_type.action.delete', '机台种类：删除', 'machine_type', '机台管理', 620),
('machine_asset.filter.keyword', '机台台账：关键词', 'machine_asset', '机台管理', 700),
('machine_asset.action.create', '机台台账：新建', 'machine_asset', '机台管理', 710),
('machine_asset.action.edit', '机台台账：编辑', 'machine_asset', '机台管理', 720),
('machine_asset.action.delete', '机台台账：删除', 'machine_asset', '机台管理', 730),
('machine_runtime.action.create', '机台运转：新建记录', 'machine_runtime', '机台管理', 800),
('machine_runtime.action.edit', '机台运转：编辑记录', 'machine_runtime', '机台管理', 810),
('machine_runtime.action.close', '机台运转：结束记录', 'machine_runtime', '机台管理', 820),
('procurement_requisition.filter.keyword', '采购请购：关键词', 'procurement_requisition', '采购管理', 900),
('procurement_requisition.action.create', '采购请购：新建', 'procurement_requisition', '采购管理', 910),
('procurement_requisition.action.edit', '采购请购：编辑', 'procurement_requisition', '采购管理', 920),
('procurement_requisition.action.delete', '采购请购：删除', 'procurement_requisition', '采购管理', 930),
('procurement_order.filter.keyword', '采购单：关键词', 'procurement_order', '采购管理', 940),
('procurement_order.action.create', '采购单：新建', 'procurement_order', '采购管理', 950),
('procurement_order.action.edit', '采购单：编辑', 'procurement_order', '采购管理', 960),
('procurement_order.action.delete', '采购单：删除', 'procurement_order', '采购管理', 970),
('procurement_order.action.detail', '采购单：详情', 'procurement_order', '采购管理', 980),
('procurement_receipt.filter.keyword', '采购收货：关键词', 'procurement_receipt', '采购管理', 990),
('procurement_receipt.action.create', '采购收货：新建', 'procurement_receipt', '采购管理', 1000),
('procurement_receipt.action.edit', '采购收货：编辑', 'procurement_receipt', '采购管理', 1010),
('procurement_receipt.action.delete', '采购收货：删除', 'procurement_receipt', '采购管理', 1020),
('procurement_stockin.filter.keyword', '采购入库：关键词', 'procurement_stockin', '采购管理', 1030),
('company.action.create', '公司主体：新建', 'company', '公司主体', 10),
('company.action.edit', '公司主体：编辑', 'company', '公司主体', 20),
('company.action.delete', '公司主体：删除', 'company', '公司主体', 30),
('user_mgmt.action.edit', '用户管理：编辑用户', 'user_mgmt', '用户管理', 10),
('role_mgmt.action.create', '角色管理：新建角色', 'role_mgmt', '角色管理', 10),
('role_mgmt.action.edit', '角色管理：编辑角色', 'role_mgmt', '角色管理', 20),
('role_mgmt.action.delete', '角色管理：删除角色', 'role_mgmt', '角色管理', 30),
('reconciliation.page.export', '对账：导出页', 'reconciliation', '对账', 10),
('reconciliation.action.download', '对账：下载文件', 'reconciliation', '对账', 20),
('openclaw.customers.read', 'OpenClaw：客户列表', 'customer', 'OpenClaw', 5),
('openclaw.customer_products.read', 'OpenClaw：客户产品列表', 'customer_product', 'OpenClaw', 6),
('openclaw.pending_items.read', 'OpenClaw：待发货明细', 'delivery', 'OpenClaw', 7),
('openclaw.order.create', 'OpenClaw：创建订单', 'order', 'OpenClaw', 8),
('openclaw.delivery.create', 'OpenClaw：创建送货单', 'delivery', 'OpenClaw', 9),
('openclaw.companies.read', 'OpenClaw：经营主体列表', 'customer', 'OpenClaw', 1),
('openclaw.products.read', 'OpenClaw：系统产品搜索', 'product', 'OpenClaw', 2),
('openclaw.customer.create', 'OpenClaw：新建客户', 'customer', 'OpenClaw', 3),
('openclaw.customer_product.create', 'OpenClaw：新建客户产品绑定', 'customer_product', 'OpenClaw', 4),
('openclaw.order.preview', 'OpenClaw：订单创建预览', 'order', 'OpenClaw', 10),
('openclaw.delivery.preview', 'OpenClaw：送货单创建预览', 'delivery', 'OpenClaw', 11);

-- 工序管理：新增能力键（与 run_40_production_process_module.sql 一致）
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('production.process_template.action.create', '工序管理：工序模板新建', 'production_process', '工序管理', 10),
('production.process_template.action.edit', '工序管理：工序模板编辑', 'production_process', '工序管理', 20),
('production.process_template.action.delete', '工序管理：工序模板删除', 'production_process', '工序管理', 30),
('production.process_routing.action.edit', '工序管理：产品路由覆写编辑', 'production_process', '工序管理', 40)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

-- 将角色 JSON 菜单导入 role_allowed_nav（与 run_17_migrate_role_json_to_nav_cap.sql 一致）
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'inventory_query' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"inventory"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'inventory_ops' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"inventory"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'report_notes' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"report_export"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'report_records' FROM `role` r
WHERE r.`allowed_menu_keys` IS NOT NULL AND JSON_CONTAINS(r.`allowed_menu_keys`, '"report_export"', '$');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, jt.`v` FROM `role` r
JOIN JSON_TABLE(r.`allowed_menu_keys`, '$[*]' COLUMNS (`v` VARCHAR(64) PATH '$')) jt
WHERE r.`allowed_menu_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_menu_keys`) = 'ARRAY'
  AND jt.`v` NOT IN ('inventory', 'report_export');

INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_department' FROM `role` r WHERE r.`code`='finance';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_employee' FROM `role` r WHERE r.`code`='finance';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_payroll' FROM `role` r WHERE r.`code`='finance';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'hr_performance' FROM `role` r WHERE r.`code`='finance';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'machine_type' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'machine_asset' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'machine_runtime' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_requisition' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_order' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_receipt' FROM `role` r WHERE r.`code`='warehouse';
INSERT IGNORE INTO `role_allowed_nav` (`role_id`, `nav_code`)
SELECT r.`id`, 'procurement_stockin' FROM `role` r WHERE r.`code`='warehouse';

-- 能力键 express.action.waybill_batch_delete（快递：单号池批量删除）
INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('express.action.waybill_batch_delete', '快递：单号池批量删除', 'express', '快递', 35)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`),
  `nav_item_code`=VALUES(`nav_item_code`),
  `group_label`=VALUES(`group_label`),
  `sort_order`=VALUES(`sort_order`);

INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT r.`id`, jt.`v` FROM `role` r
JOIN JSON_TABLE(r.`allowed_capability_keys`, '$[*]' COLUMNS (`v` VARCHAR(128) PATH '$')) jt
WHERE r.`allowed_capability_keys` IS NOT NULL
  AND JSON_TYPE(r.`allowed_capability_keys`) = 'ARRAY'
  AND JSON_LENGTH(r.`allowed_capability_keys`) > 0;

-- 与 run_22 一致：拥有「删除进出明细」的角色同步获得「撤销手工/导入批次」
INSERT IGNORE INTO `role_allowed_capability` (`role_id`, `cap_code`)
SELECT `role_id`, 'inventory_ops.movement_batch.void'
FROM `role_allowed_capability`
WHERE `cap_code` = 'inventory_ops.movement.delete';
