-- OpenClaw 确认制流程：主体/产品查询、创建客户与客户产品、订单/送货预览（可重复执行）
USE sydixon_order;
SET NAMES utf8mb4;

INSERT INTO `sys_capability` (`code`, `title`, `nav_item_code`, `group_label`, `sort_order`) VALUES
('openclaw.companies.read', 'OpenClaw：经营主体列表', 'customer', 'OpenClaw', 1),
('openclaw.products.read', 'OpenClaw：系统产品搜索', 'product', 'OpenClaw', 2),
('openclaw.customer.create', 'OpenClaw：新建客户', 'customer', 'OpenClaw', 3),
('openclaw.customer_product.create', 'OpenClaw：新建客户产品绑定', 'customer_product', 'OpenClaw', 4),
('openclaw.order.preview', 'OpenClaw：订单创建预览', 'order', 'OpenClaw', 10),
('openclaw.delivery.preview', 'OpenClaw：送货单创建预览', 'delivery', 'OpenClaw', 11)
ON DUPLICATE KEY UPDATE
  `title` = VALUES(`title`),
  `nav_item_code` = VALUES(`nav_item_code`),
  `group_label` = VALUES(`group_label`),
  `sort_order` = VALUES(`sort_order`);
