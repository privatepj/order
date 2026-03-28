-- 导航与能力全量种子（与 app/auth 逻辑一致；可重复执行时用 DELETE+INSERT 或改 ON DUPLICATE）
USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_nav_item` (`id`, `parent_id`, `code`, `title`, `endpoint`, `sort_order`, `is_active`, `admin_only`, `is_assignable`, `landing_priority`) VALUES
(1, NULL, 'order', '订单', 'main.order_list', 10, 1, 0, 1, 10),
(2, NULL, 'nav_warehouse', '仓管', NULL, 20, 1, 0, 0, NULL),
(3, 2, 'delivery', '送货', 'main.delivery_list', 10, 1, 0, 1, 20),
(4, 2, 'express', '快递', 'main.express_company_list', 20, 1, 0, 1, 80),
(5, 2, 'inventory_query', '库存查询', 'main.inventory_stock_query', 30, 1, 0, 1, 85),
(6, 2, 'inventory_ops', '库存录入', 'main.inventory_list', 40, 1, 0, 1, 86),
(7, NULL, 'nav_base', '基础数据', NULL, 30, 1, 0, 0, NULL),
(8, 7, 'customer', '客户', 'main.customer_list', 10, 1, 0, 1, 30),
(9, 7, 'product', '产品', 'main.product_list', 20, 1, 0, 1, 40),
(10, 7, 'customer_product', '客户产品', 'main.customer_product_list', 30, 1, 0, 1, 50),
(11, 7, 'company', '公司主体', 'main.company_list', 40, 1, 1, 1, 90),
(12, 7, 'user_mgmt', '用户管理', 'main.user_list', 50, 1, 1, 1, 100),
(13, 7, 'role_mgmt', '角色管理', 'main.role_list', 60, 1, 1, 1, 101),
(14, NULL, 'nav_finance', '财务', NULL, 40, 1, 0, 0, NULL),
(15, 14, 'reconciliation', '对账导出', 'main.reconciliation_export', 10, 1, 0, 1, 60),
(16, NULL, 'nav_report', '报表导出', NULL, 50, 1, 0, 0, NULL),
(17, 16, 'report_notes', '导出送货单Excel', 'main.report_export_delivery_notes', 10, 1, 0, 1, 70),
(18, 16, 'report_records', '导出送货记录Excel', 'main.report_export_delivery_records', 20, 1, 0, 1, 71)
ON DUPLICATE KEY UPDATE
  `title`=VALUES(`title`), `endpoint`=VALUES(`endpoint`), `sort_order`=VALUES(`sort_order`),
  `admin_only`=VALUES(`admin_only`), `is_assignable`=VALUES(`is_assignable`), `landing_priority`=VALUES(`landing_priority`);

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
-- 订单
('order.filter.customer', '订单列表：按客户筛选', 'order', '订单', 10),
('order.filter.status', '订单列表：按状态筛选', 'order', '订单', 20),
('order.filter.payment_type', '订单列表：按付款类型筛选', 'order', '订单', 30),
('order.filter.keyword', '订单列表：关键词搜索', 'order', '订单', 40),
('order.action.create', '订单：新建', 'order', '订单', 50),
('order.action.edit', '订单：编辑', 'order', '订单', 60),
('order.action.delete', '订单：删除', 'order', '订单', 70),
-- 客户产品
('customer_product.filter.customer', '客户产品列表：按客户筛选', 'customer_product', '客户产品', 10),
('customer_product.filter.keyword', '客户产品列表：关键词搜索', 'customer_product', '客户产品', 20),
('customer_product.action.create', '客户产品：新建', 'customer_product', '客户产品', 30),
('customer_product.action.edit', '客户产品：编辑', 'customer_product', '客户产品', 40),
('customer_product.action.delete', '客户产品：删除', 'customer_product', '客户产品', 50),
('customer_product.action.import', '客户产品：Excel 导入', 'customer_product', '客户产品', 60),
('customer_product.action.export_template', '客户产品：下载导入模板', 'customer_product', '客户产品', 70),
-- 送货
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
('delivery.api.customers_search', '送货：客户搜索接口', 'delivery', '送货', 120),
('delivery.api.pending_items', '送货：待送明细接口', 'delivery', '送货', 130),
('delivery.api.next_waybill', '送货：取单号接口', 'delivery', '送货', 140),
-- 报表导出-送货单
('report_notes.page.view', '报表：送货单导出页', 'report_notes', '报表导出', 10),
('report_notes.export.run', '报表：执行导出送货单', 'report_notes', '报表导出', 20),
-- 报表导出-送货记录
('report_records.page.view', '报表：送货记录导出页', 'report_records', '报表导出', 10),
('report_records.export.run', '报表：执行导出送货记录', 'report_records', '报表导出', 20),
-- 快递
('express.action.company_create', '快递：新建快递公司', 'express', '快递', 10),
('express.action.company_edit', '快递：编辑快递公司', 'express', '快递', 20),
('express.action.waybill_import', '快递：单号池导入', 'express', '快递', 30),
-- 库存查询
('inventory_query.filter.category', '库存查询：类别', 'inventory_query', '库存查询', 10),
('inventory_query.filter.spec', '库存查询：规格', 'inventory_query', '库存查询', 20),
('inventory_query.filter.name_spec', '库存查询：品名/规格/编号', 'inventory_query', '库存查询', 30),
('inventory_query.filter.storage_area', '库存查询：仓储区', 'inventory_query', '库存查询', 40),
-- 库存录入
('inventory_ops.api.products_search', '库存录入：产品搜索接口', 'inventory_ops', '库存录入', 10),
('inventory_ops.api.suggest_storage_area', '库存录入：仓储区建议接口', 'inventory_ops', '库存录入', 20),
('inventory_ops.movement.list', '库存录入：流水列表', 'inventory_ops', '库存录入', 25),
('inventory_ops.movement.create', '库存录入：手工出入库', 'inventory_ops', '库存录入', 30),
('inventory_ops.movement.delete', '库存录入：删除进出明细', 'inventory_ops', '库存录入', 40),
('inventory_ops.opening.list', '库存录入：期初列表', 'inventory_ops', '库存录入', 50),
('inventory_ops.opening.create', '库存录入：新建期初', 'inventory_ops', '库存录入', 60),
('inventory_ops.opening.edit', '库存录入：编辑期初', 'inventory_ops', '库存录入', 70),
('inventory_ops.opening.delete', '库存录入：删除期初', 'inventory_ops', '库存录入', 80),
('inventory_ops.daily.list', '库存录入：日结列表', 'inventory_ops', '库存录入', 90),
('inventory_ops.daily.create', '库存录入：新建日结', 'inventory_ops', '库存录入', 100),
('inventory_ops.daily.detail', '库存录入：日结详情', 'inventory_ops', '库存录入', 110),
('inventory_ops.daily.edit', '库存录入：编辑日结', 'inventory_ops', '库存录入', 120),
('inventory_ops.daily.delete', '库存录入：删除日结', 'inventory_ops', '库存录入', 130),
-- 客户
('customer.filter.keyword', '客户列表：关键词搜索', 'customer', '客户', 10),
('customer.action.create', '客户：新建', 'customer', '客户', 20),
('customer.action.edit', '客户：编辑', 'customer', '客户', 30),
('customer.action.delete', '客户：删除', 'customer', '客户', 40),
('customer.action.import', '客户：Excel 导入', 'customer', '客户', 50),
-- 产品
('product.filter.keyword', '产品列表：关键词搜索', 'product', '产品', 10),
('product.action.create', '产品：新建', 'product', '产品', 20),
('product.action.edit', '产品：编辑', 'product', '产品', 30),
('product.action.delete', '产品：删除', 'product', '产品', 40),
('product.action.import', '产品：Excel 导入', 'product', '产品', 50),
-- 公司主体
('company.action.create', '公司主体：新建', 'company', '公司主体', 10),
('company.action.edit', '公司主体：编辑', 'company', '公司主体', 20),
('company.action.delete', '公司主体：删除', 'company', '公司主体', 30),
-- 用户
('user_mgmt.action.edit', '用户管理：编辑用户', 'user_mgmt', '用户管理', 10),
-- 角色
('role_mgmt.action.create', '角色管理：新建角色', 'role_mgmt', '角色管理', 10),
('role_mgmt.action.edit', '角色管理：编辑角色', 'role_mgmt', '角色管理', 20),
('role_mgmt.action.delete', '角色管理：删除角色', 'role_mgmt', '角色管理', 30),
-- 对账
('reconciliation.page.export', '对账：导出页', 'reconciliation', '对账', 10),
('reconciliation.action.download', '对账：下载文件', 'reconciliation', '对账', 20)
ON DUPLICATE KEY UPDATE `title`=VALUES(`title`), `nav_item_code`=VALUES(`nav_item_code`), `group_label`=VALUES(`group_label`), `sort_order`=VALUES(`sort_order`);
