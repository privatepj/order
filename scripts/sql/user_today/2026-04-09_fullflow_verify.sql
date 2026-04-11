-- Verification script for FF26 full-flow seed data

SET NAMES utf8mb4;

SET @company_id := COALESCE(
  (SELECT id FROM company WHERE is_default = 1 ORDER BY id ASC LIMIT 1),
  (SELECT id FROM company ORDER BY id ASC LIMIT 1)
);

SELECT 'company_id' AS item, @company_id AS value;

SELECT
  'master_counts' AS section,
  (SELECT COUNT(*) FROM customer WHERE customer_code LIKE 'FF26_%') AS customer_cnt,
  (SELECT COUNT(*) FROM product WHERE product_code LIKE 'FF26_%') AS product_cnt,
  (SELECT COUNT(*) FROM customer_product cp JOIN customer c ON c.id = cp.customer_id JOIN product p ON p.id = cp.product_id WHERE c.customer_code LIKE 'FF26_%' AND p.product_code LIKE 'FF26_%') AS customer_product_cnt,
  (SELECT COUNT(*) FROM semi_material WHERE code LIKE 'FF26_%') AS semi_material_cnt,
  (SELECT COUNT(*) FROM bom_header bh JOIN product p ON p.id = bh.parent_product_id WHERE p.product_code = 'FF26_PROD_001' AND bh.parent_kind = 'finished' AND bh.is_active = 1) AS bom_finished_active_cnt;

SELECT
  'resource_counts' AS section,
  (SELECT COUNT(*) FROM hr_department WHERE company_id = @company_id AND name = 'FF26 Dept Assembly') AS dept_cnt,
  (SELECT COUNT(*) FROM hr_work_type WHERE company_id = @company_id AND name = 'FF26 WorkType Assembly') AS work_type_cnt,
  (SELECT COUNT(*) FROM hr_employee WHERE company_id = @company_id AND employee_no = 'FF26E001') AS employee_cnt,
  (SELECT COUNT(*) FROM hr_employee_capability c JOIN hr_employee e ON e.id = c.employee_id WHERE e.company_id = @company_id AND e.employee_no = 'FF26E001') AS capability_cnt,
  (SELECT COUNT(*) FROM machine_type WHERE code = 'FF26_MTYPE_01') AS machine_type_cnt,
  (SELECT COUNT(*) FROM machine WHERE machine_no = 'FF26_MC_001') AS machine_cnt,
  (SELECT COUNT(*) FROM machine_operator_allowlist a JOIN machine m ON m.id = a.machine_id WHERE m.machine_no = 'FF26_MC_001' AND a.is_active = 1) AS allowlist_cnt,
  (SELECT COUNT(*) FROM machine_schedule_booking b JOIN machine_schedule_template t ON t.id = b.template_id JOIN machine m ON m.id = b.machine_id WHERE m.machine_no = 'FF26_MC_001' AND t.name = 'FF26 Machine Template' AND b.state = 'available' AND b.start_at >= CURDATE()) AS future_machine_booking_cnt;

SELECT
  'process_counts' AS section,
  (SELECT COUNT(*) FROM production_process_template WHERE name = 'FF26 Process Template 001' AND version = 'v1' AND is_active = 1) AS process_template_cnt,
  (SELECT COUNT(*) FROM production_process_template_step s JOIN production_process_template t ON t.id = s.template_id WHERE t.name = 'FF26 Process Template 001' AND t.version = 'v1') AS process_step_cnt,
  (SELECT COUNT(*) FROM production_product_routing r JOIN product p ON p.id = r.product_id WHERE p.product_code = 'FF26_PROD_001' AND r.is_active = 1) AS routing_cnt,
  (SELECT COUNT(*) FROM production_preplan pp WHERE pp.remark = 'FF26_PREPLAN_TODO' AND pp.customer_id = (SELECT id FROM customer WHERE customer_code = 'FF26_CUST_001' LIMIT 1)) AS preplan_todo_cnt;

SELECT
  'supplier_procurement_base' AS section,
  (SELECT COUNT(*) FROM supplier WHERE company_id = @company_id AND name LIKE 'FF26 Supplier %') AS supplier_cnt,
  (SELECT COUNT(*) FROM supplier_material_map sm JOIN supplier s ON s.id = sm.supplier_id JOIN semi_material m ON m.id = sm.material_id WHERE s.company_id = @company_id AND s.name LIKE 'FF26 Supplier %' AND m.code LIKE 'FF26_%') AS supplier_material_map_cnt,
  (SELECT COUNT(*) FROM supplier_material_map sm JOIN semi_material m ON m.id = sm.material_id WHERE m.code = 'FF26_MAT_001' AND sm.is_preferred = 1 AND sm.is_active = 1) AS mat_a_preferred_supplier_cnt;

SELECT
  'pending_chain' AS section,
  so.id AS sales_order_id,
  so.status AS sales_order_status,
  oi.id AS order_item_id,
  oi.quantity AS order_item_qty,
  req.id AS requisition_id,
  req.status AS requisition_status,
  req_line.id AS requisition_line_id,
  req_line.status AS requisition_line_status,
  req_line.qty AS requisition_line_qty,
  (
    SELECT COUNT(*)
    FROM purchase_order po
    WHERE po.requisition_id = req.id
      AND po.po_no LIKE 'FF26_PO_TODO_%'
  ) AS generated_todo_po_cnt
FROM sales_order so
LEFT JOIN order_item oi ON oi.order_id = so.id
LEFT JOIN purchase_requisition req ON req.req_no = 'FF26_REQ_TODO_001'
LEFT JOIN purchase_requisition_line req_line ON req_line.requisition_id = req.id AND req_line.line_no = 1
WHERE so.order_no = 'FF26_SO_TODO_001';

SELECT
  'done_chain' AS section,
  req.id AS requisition_id,
  req.status AS requisition_status,
  req_line.id AS requisition_line_id,
  req_line.status AS requisition_line_status,
  po.id AS purchase_order_id,
  po.status AS purchase_order_status,
  po.reconcile_status AS po_reconcile_status,
  rcv.id AS receipt_id,
  rcv.status AS receipt_status,
  rcv.reconcile_status AS receipt_reconcile_status,
  sin.id AS stock_in_id,
  sin.approval_status AS stock_in_status,
  sin.qty AS stock_in_qty,
  sin.received_qty AS stock_in_received_qty,
  sin.warehouse_qty AS stock_in_warehouse_qty,
  IFNULL(mov.mov_qty, 0) AS inventory_in_qty
FROM purchase_requisition req
LEFT JOIN purchase_requisition_line req_line ON req_line.requisition_id = req.id AND req_line.line_no = 1
LEFT JOIN purchase_order po ON po.po_no = 'FF26_PO_DONE_001'
LEFT JOIN purchase_receipt rcv ON rcv.receipt_no = 'FF26_RCV_DONE_001'
LEFT JOIN purchase_stock_in sin ON sin.stock_in_no = 'FF26_SIN_DONE_001'
LEFT JOIN (
  SELECT source_purchase_receipt_id, SUM(quantity) AS mov_qty
  FROM inventory_movement
  WHERE source_type = 'procurement' AND direction = 'in'
  GROUP BY source_purchase_receipt_id
) mov ON mov.source_purchase_receipt_id = rcv.id
WHERE req.req_no = 'FF26_REQ_DONE_001';

SELECT
  'assertions' AS section,
  CASE WHEN EXISTS (SELECT 1 FROM customer WHERE customer_code = 'FF26_CUST_001') THEN 'PASS' ELSE 'FAIL' END AS customer_ready,
  CASE WHEN EXISTS (SELECT 1 FROM product WHERE product_code = 'FF26_PROD_001') THEN 'PASS' ELSE 'FAIL' END AS product_ready,
  CASE WHEN EXISTS (SELECT 1 FROM production_product_routing r JOIN product p ON p.id = r.product_id WHERE p.product_code = 'FF26_PROD_001' AND r.is_active = 1) THEN 'PASS' ELSE 'FAIL' END AS routing_ready,
  CASE WHEN EXISTS (SELECT 1 FROM machine_schedule_booking b JOIN machine m ON m.id = b.machine_id WHERE m.machine_no = 'FF26_MC_001' AND b.state = 'available' AND b.start_at >= CURDATE()) THEN 'PASS' ELSE 'FAIL' END AS machine_booking_ready,
  CASE WHEN EXISTS (SELECT 1 FROM purchase_requisition WHERE req_no = 'FF26_REQ_TODO_001' AND status = 'signed') THEN 'PASS' ELSE 'FAIL' END AS pending_requisition_ready,
  CASE WHEN EXISTS (SELECT 1 FROM purchase_order WHERE po_no = 'FF26_PO_DONE_001' AND status = 'received') THEN 'PASS' ELSE 'FAIL' END AS done_po_ready,
  CASE WHEN EXISTS (SELECT 1 FROM purchase_receipt WHERE receipt_no = 'FF26_RCV_DONE_001' AND status = 'posted') THEN 'PASS' ELSE 'FAIL' END AS done_receipt_ready,
  CASE WHEN EXISTS (SELECT 1 FROM purchase_stock_in WHERE stock_in_no = 'FF26_SIN_DONE_001' AND approval_status = 'matched') THEN 'PASS' ELSE 'FAIL' END AS done_stockin_ready;
