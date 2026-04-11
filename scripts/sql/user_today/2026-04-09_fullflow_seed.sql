-- Full-flow seed data for integrated manual verification
-- Prefix convention: FF26_
-- Safe to re-run: uses upsert/conditional insert logic and isolated keys.

SET NAMES utf8mb4;

SET @seed_prefix := 'FF26_';
SET @today := CURDATE();
SET @admin_user_id := IFNULL((SELECT id FROM `user` WHERE username = 'admin' ORDER BY id ASC LIMIT 1), 1);
SET @company_id := COALESCE(
  (SELECT id FROM company WHERE is_default = 1 ORDER BY id ASC LIMIT 1),
  (SELECT id FROM company ORDER BY id ASC LIMIT 1)
);

-- ------------------------------------------------------------------
-- 1) Master data: customer/product/customer_product/semi-material/BOM
-- ------------------------------------------------------------------

INSERT INTO customer (
  customer_code, short_code, name, contact, phone, address, payment_terms, remark, company_id, tax_point
)
VALUES (
  'FF26_CUST_001', 'FF26C1', 'FF26 Demo Customer', 'FF26 Contact', '13800000026',
  'FF26 Demo Address', 'monthly', 'FF26 seed customer', @company_id, 0.1300
)
ON DUPLICATE KEY UPDATE
  short_code = VALUES(short_code),
  name = VALUES(name),
  contact = VALUES(contact),
  phone = VALUES(phone),
  address = VALUES(address),
  payment_terms = VALUES(payment_terms),
  remark = VALUES(remark),
  company_id = VALUES(company_id),
  tax_point = VALUES(tax_point);

SET @cust_id := (SELECT id FROM customer WHERE customer_code = 'FF26_CUST_001' LIMIT 1);

INSERT INTO product (
  product_code, name, spec, base_unit, remark
)
VALUES (
  'FF26_PROD_001', 'FF26 Finished Product A', 'FF26-SPEC-A', 'pcs', 'FF26 seed product'
)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  spec = VALUES(spec),
  base_unit = VALUES(base_unit),
  remark = VALUES(remark);

SET @prod_id := (SELECT id FROM product WHERE product_code = 'FF26_PROD_001' LIMIT 1);

SET @cp_id := (
  SELECT id FROM customer_product
  WHERE customer_id = @cust_id AND product_id = @prod_id
  ORDER BY id DESC
  LIMIT 1
);

INSERT INTO customer_product (
  customer_id, product_id, customer_material_no, material_no, unit, price, currency, remark
)
SELECT
  @cust_id,
  @prod_id,
  'FF26-CMAT-001',
  'FF26_PROD_001',
  'pcs',
  12.5000,
  'CNY',
  'FF26 seed customer-product mapping'
WHERE @cp_id IS NULL;

SET @cp_id := (
  SELECT id FROM customer_product
  WHERE customer_id = @cust_id AND product_id = @prod_id
  ORDER BY id DESC
  LIMIT 1
);

UPDATE customer_product
SET
  customer_material_no = 'FF26-CMAT-001',
  material_no = 'FF26_PROD_001',
  unit = 'pcs',
  price = 12.5000,
  currency = 'CNY',
  remark = 'FF26 seed customer-product mapping'
WHERE id = @cp_id;

INSERT INTO semi_material (kind, code, name, spec, base_unit, standard_unit_cost, remark)
VALUES
  ('semi', 'FF26_SEMI_001', 'FF26 Semi Product A', 'FF26-SEMI-SPEC', 'pcs', 18.0000, 'FF26 semi for BOM'),
  ('material', 'FF26_MAT_001', 'FF26 Raw Material A', 'FF26-MAT-A', 'kg', 8.8000, 'FF26 material A'),
  ('material', 'FF26_MAT_002', 'FF26 Raw Material B', 'FF26-MAT-B', 'kg', 4.5000, 'FF26 material B'),
  ('material', 'FF26_MAT_DONE_001', 'FF26 Raw Material Done Sample', 'FF26-MAT-DONE', 'kg', 6.0000, 'FF26 done sample material')
ON DUPLICATE KEY UPDATE
  kind = VALUES(kind),
  name = VALUES(name),
  spec = VALUES(spec),
  base_unit = VALUES(base_unit),
  standard_unit_cost = VALUES(standard_unit_cost),
  remark = VALUES(remark);

SET @semi_id := (SELECT id FROM semi_material WHERE code = 'FF26_SEMI_001' LIMIT 1);
SET @mat_a_id := (SELECT id FROM semi_material WHERE code = 'FF26_MAT_001' LIMIT 1);
SET @mat_b_id := (SELECT id FROM semi_material WHERE code = 'FF26_MAT_002' LIMIT 1);
SET @mat_done_id := (SELECT id FROM semi_material WHERE code = 'FF26_MAT_DONE_001' LIMIT 1);

INSERT INTO bom_header (
  parent_kind, parent_product_id, parent_material_id, version_no, is_active, remark
)
VALUES (
  'finished', @prod_id, 0, 1, 1, 'FF26 active BOM for finished product'
)
ON DUPLICATE KEY UPDATE
  is_active = VALUES(is_active),
  remark = VALUES(remark);

SET @bom_finished_id := (
  SELECT id FROM bom_header
  WHERE parent_kind = 'finished' AND parent_product_id = @prod_id AND parent_material_id = 0 AND version_no = 1
  LIMIT 1
);

DELETE FROM bom_line WHERE bom_header_id = @bom_finished_id;

INSERT INTO bom_line (
  bom_header_id, line_no, child_kind, child_material_id, quantity, unit, remark
)
VALUES
  (@bom_finished_id, 1, 'semi', @semi_id, 1.0000, 'pcs', 'FF26 finished->semi'),
  (@bom_finished_id, 2, 'material', @mat_b_id, 2.0000, 'kg', 'FF26 finished->rawB');

INSERT INTO bom_header (
  parent_kind, parent_product_id, parent_material_id, version_no, is_active, remark
)
VALUES (
  'semi', 0, @semi_id, 1, 1, 'FF26 active BOM for semi'
)
ON DUPLICATE KEY UPDATE
  is_active = VALUES(is_active),
  remark = VALUES(remark);

SET @bom_semi_id := (
  SELECT id FROM bom_header
  WHERE parent_kind = 'semi' AND parent_product_id = 0 AND parent_material_id = @semi_id AND version_no = 1
  LIMIT 1
);

DELETE FROM bom_line WHERE bom_header_id = @bom_semi_id;

INSERT INTO bom_line (
  bom_header_id, line_no, child_kind, child_material_id, quantity, unit, remark
)
VALUES
  (@bom_semi_id, 1, 'material', @mat_a_id, 3.0000, 'kg', 'FF26 semi->rawA');

-- ------------------------------------------------------------------
-- 2) Process & resources: work type/employee/capability/machine/schedule
-- ------------------------------------------------------------------

INSERT INTO hr_department (company_id, name, sort_order)
VALUES (@company_id, 'FF26 Dept Assembly', 260)
ON DUPLICATE KEY UPDATE
  sort_order = VALUES(sort_order);

SET @dept_id := (
  SELECT id FROM hr_department
  WHERE company_id = @company_id AND name = 'FF26 Dept Assembly'
  LIMIT 1
);

INSERT INTO hr_work_type (company_id, name, sort_order, is_active, remark)
VALUES (@company_id, 'FF26 WorkType Assembly', 260, 1, 'FF26 seed work type')
ON DUPLICATE KEY UPDATE
  sort_order = VALUES(sort_order),
  is_active = VALUES(is_active),
  remark = VALUES(remark);

SET @work_type_id := (
  SELECT id FROM hr_work_type
  WHERE company_id = @company_id AND name = 'FF26 WorkType Assembly'
  LIMIT 1
);

INSERT INTO hr_department_work_type_map (
  company_id, department_id, work_type_id, is_active, remark
)
VALUES (
  @company_id, @dept_id, @work_type_id, 1, 'FF26 dept-worktype mapping'
)
ON DUPLICATE KEY UPDATE
  is_active = VALUES(is_active),
  remark = VALUES(remark);

INSERT INTO hr_employee (
  company_id, department_id, user_id, employee_no, name, phone, job_title,
  main_work_type_id, status, hire_date, leave_date, remark
)
VALUES (
  @company_id, @dept_id, NULL, 'FF26E001', 'FF26 Operator 01', '13800002601', 'FF26 Operator',
  @work_type_id, 'active', @today, NULL, 'FF26 seed operator'
)
ON DUPLICATE KEY UPDATE
  department_id = VALUES(department_id),
  user_id = VALUES(user_id),
  name = VALUES(name),
  phone = VALUES(phone),
  job_title = VALUES(job_title),
  main_work_type_id = VALUES(main_work_type_id),
  status = VALUES(status),
  hire_date = VALUES(hire_date),
  leave_date = VALUES(leave_date),
  remark = VALUES(remark);

SET @emp_id := (
  SELECT id FROM hr_employee
  WHERE company_id = @company_id AND employee_no = 'FF26E001'
  LIMIT 1
);

INSERT INTO hr_employee_work_type (employee_id, work_type_id, is_primary)
VALUES (@emp_id, @work_type_id, 1)
ON DUPLICATE KEY UPDATE
  is_primary = VALUES(is_primary);

INSERT INTO hr_employee_capability (
  company_id, employee_id, hr_department_id, work_type_id,
  good_qty_total, bad_qty_total, produced_qty_total,
  work_order_cnt_total, worked_minutes_total, labor_cost_total, processed_to
)
VALUES (
  @company_id, @emp_id, @dept_id, @work_type_id,
  480.0000, 20.0000, 500.0000,
  8, 3000.0000, 1200.00, NOW()
)
ON DUPLICATE KEY UPDATE
  work_type_id = VALUES(work_type_id),
  good_qty_total = VALUES(good_qty_total),
  bad_qty_total = VALUES(bad_qty_total),
  produced_qty_total = VALUES(produced_qty_total),
  work_order_cnt_total = VALUES(work_order_cnt_total),
  worked_minutes_total = VALUES(worked_minutes_total),
  labor_cost_total = VALUES(labor_cost_total),
  processed_to = VALUES(processed_to);

INSERT INTO machine_type (
  code, name, is_active, remark, default_capability_hr_department_id, default_capability_work_type_id
)
VALUES (
  'FF26_MTYPE_01', 'FF26 Machine Type 01', 1, 'FF26 seed machine type', 0, @work_type_id
)
ON DUPLICATE KEY UPDATE
  is_active = VALUES(is_active),
  remark = VALUES(remark),
  default_capability_hr_department_id = VALUES(default_capability_hr_department_id),
  default_capability_work_type_id = VALUES(default_capability_work_type_id);

SET @machine_type_id := (SELECT id FROM machine_type WHERE code = 'FF26_MTYPE_01' LIMIT 1);

INSERT INTO machine (
  machine_no, name, machine_type_id, capacity_per_hour,
  machine_cost_purchase_price, machine_accum_produced_qty, machine_accum_runtime_hours,
  machine_single_run_cost, status, location, owner_user_id, remark,
  default_capability_hr_department_id, default_capability_work_type_id
)
VALUES (
  'FF26_MC_001', 'FF26 Machine 01', @machine_type_id, 120.00,
  10000.00, 0.0000, 0.0000,
  110.00, 'enabled', 'FF26-Workshop-A', @admin_user_id, 'FF26 seed machine',
  0, @work_type_id
)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  machine_type_id = VALUES(machine_type_id),
  capacity_per_hour = VALUES(capacity_per_hour),
  machine_cost_purchase_price = VALUES(machine_cost_purchase_price),
  machine_single_run_cost = VALUES(machine_single_run_cost),
  status = VALUES(status),
  location = VALUES(location),
  owner_user_id = VALUES(owner_user_id),
  remark = VALUES(remark),
  default_capability_hr_department_id = VALUES(default_capability_hr_department_id),
  default_capability_work_type_id = VALUES(default_capability_work_type_id);

SET @machine_id := (SELECT id FROM machine WHERE machine_no = 'FF26_MC_001' LIMIT 1);

INSERT INTO machine_operator_allowlist (
  machine_id, employee_id, capability_hr_department_id, capability_work_type_id, is_active, remark
)
VALUES (
  @machine_id, @emp_id, 0, @work_type_id, 1, 'FF26 machine-operator allowlist'
)
ON DUPLICATE KEY UPDATE
  capability_hr_department_id = VALUES(capability_hr_department_id),
  capability_work_type_id = VALUES(capability_work_type_id),
  is_active = VALUES(is_active),
  remark = VALUES(remark);

SET @machine_tpl_id := (
  SELECT id FROM machine_schedule_template
  WHERE machine_id = @machine_id AND name = 'FF26 Machine Template'
  ORDER BY id ASC
  LIMIT 1
);

INSERT INTO machine_schedule_template (
  machine_id, name, repeat_kind, days_of_week, valid_from, valid_to,
  start_time, end_time, state, remark, created_by
)
SELECT
  @machine_id, 'FF26 Machine Template', 'weekly', '0,1,2,3,4,5,6', @today, DATE_ADD(@today, INTERVAL 30 DAY),
  '08:00:00', '20:00:00', 'available', 'FF26 machine schedule template', @admin_user_id
WHERE @machine_tpl_id IS NULL;

SET @machine_tpl_id := (
  SELECT id FROM machine_schedule_template
  WHERE machine_id = @machine_id AND name = 'FF26 Machine Template'
  ORDER BY id ASC
  LIMIT 1
);

UPDATE machine_schedule_template
SET
  repeat_kind = 'weekly',
  days_of_week = '0,1,2,3,4,5,6',
  valid_from = @today,
  valid_to = DATE_ADD(@today, INTERVAL 30 DAY),
  start_time = '08:00:00',
  end_time = '20:00:00',
  state = 'available',
  remark = 'FF26 machine schedule template',
  created_by = COALESCE(created_by, @admin_user_id)
WHERE id = @machine_tpl_id;

SET @d0 := @today;
SET @d1 := DATE_ADD(@today, INTERVAL 1 DAY);
SET @d2 := DATE_ADD(@today, INTERVAL 2 DAY);
SET @d3 := DATE_ADD(@today, INTERVAL 3 DAY);
SET @d4 := DATE_ADD(@today, INTERVAL 4 DAY);
SET @d5 := DATE_ADD(@today, INTERVAL 5 DAY);
SET @d6 := DATE_ADD(@today, INTERVAL 6 DAY);
SET @d7 := DATE_ADD(@today, INTERVAL 7 DAY);
SET @d8 := DATE_ADD(@today, INTERVAL 8 DAY);
SET @d9 := DATE_ADD(@today, INTERVAL 9 DAY);

INSERT INTO machine_schedule_booking (
  machine_id, template_id, state, start_at, end_at, remark, created_by
)
SELECT
  @machine_id,
  @machine_tpl_id,
  'available',
  TIMESTAMP(ds.biz_date, '08:00:00'),
  TIMESTAMP(ds.biz_date, '20:00:00'),
  'FF26 auto booking window',
  @admin_user_id
FROM (
  SELECT @d0 AS biz_date UNION ALL
  SELECT @d1 UNION ALL
  SELECT @d2 UNION ALL
  SELECT @d3 UNION ALL
  SELECT @d4 UNION ALL
  SELECT @d5 UNION ALL
  SELECT @d6 UNION ALL
  SELECT @d7 UNION ALL
  SELECT @d8 UNION ALL
  SELECT @d9
) ds
WHERE NOT EXISTS (
  SELECT 1
  FROM machine_schedule_booking b
  WHERE b.template_id = @machine_tpl_id
    AND b.start_at = TIMESTAMP(ds.biz_date, '08:00:00')
);

SET @emp_tpl_id := (
  SELECT id FROM hr_employee_schedule_template
  WHERE employee_id = @emp_id AND name = 'FF26 Employee Template'
  ORDER BY id ASC
  LIMIT 1
);

INSERT INTO hr_employee_schedule_template (
  employee_id, name, repeat_kind, days_of_week, valid_from, valid_to,
  start_time, end_time, state, remark, created_by
)
SELECT
  @emp_id, 'FF26 Employee Template', 'weekly', '0,1,2,3,4,5,6', @today, DATE_ADD(@today, INTERVAL 30 DAY),
  '08:00:00', '20:00:00', 'available', 'FF26 employee schedule template', @admin_user_id
WHERE @emp_tpl_id IS NULL;

SET @emp_tpl_id := (
  SELECT id FROM hr_employee_schedule_template
  WHERE employee_id = @emp_id AND name = 'FF26 Employee Template'
  ORDER BY id ASC
  LIMIT 1
);

UPDATE hr_employee_schedule_template
SET
  repeat_kind = 'weekly',
  days_of_week = '0,1,2,3,4,5,6',
  valid_from = @today,
  valid_to = DATE_ADD(@today, INTERVAL 30 DAY),
  start_time = '08:00:00',
  end_time = '20:00:00',
  state = 'available',
  remark = 'FF26 employee schedule template',
  created_by = COALESCE(created_by, @admin_user_id)
WHERE id = @emp_tpl_id;

INSERT INTO hr_employee_schedule_booking (
  employee_id, template_id, state, start_at, end_at, remark, created_by,
  hr_department_id, work_type_id, work_order_id, product_id, unit,
  good_qty, bad_qty, produced_qty
)
SELECT
  @emp_id,
  @emp_tpl_id,
  'available',
  TIMESTAMP(ds.biz_date, '08:00:00'),
  TIMESTAMP(ds.biz_date, '20:00:00'),
  'FF26 auto employee booking',
  @admin_user_id,
  @dept_id,
  @work_type_id,
  NULL,
  NULL,
  NULL,
  0,
  0,
  0
FROM (
  SELECT @d0 AS biz_date UNION ALL
  SELECT @d1 UNION ALL
  SELECT @d2 UNION ALL
  SELECT @d3 UNION ALL
  SELECT @d4 UNION ALL
  SELECT @d5 UNION ALL
  SELECT @d6 UNION ALL
  SELECT @d7 UNION ALL
  SELECT @d8 UNION ALL
  SELECT @d9
) ds
WHERE NOT EXISTS (
  SELECT 1
  FROM hr_employee_schedule_booking b
  WHERE b.employee_id = @emp_id
    AND b.template_id = @emp_tpl_id
    AND b.start_at = TIMESTAMP(ds.biz_date, '08:00:00')
);

-- ------------------------------------------------------------------
-- 3) Process template and product routing
-- ------------------------------------------------------------------

SET @proc_tpl_id := (
  SELECT id FROM production_process_template
  WHERE name = 'FF26 Process Template 001' AND version = 'v1'
  ORDER BY id ASC
  LIMIT 1
);

INSERT INTO production_process_template (
  name, version, is_active, remark, created_by
)
SELECT
  'FF26 Process Template 001', 'v1', 1, 'FF26 process template', @admin_user_id
WHERE @proc_tpl_id IS NULL;

SET @proc_tpl_id := (
  SELECT id FROM production_process_template
  WHERE name = 'FF26 Process Template 001' AND version = 'v1'
  ORDER BY id ASC
  LIMIT 1
);

UPDATE production_process_template
SET
  is_active = 1,
  remark = 'FF26 process template',
  created_by = COALESCE(created_by, @admin_user_id)
WHERE id = @proc_tpl_id;

DELETE FROM production_process_template_step WHERE template_id = @proc_tpl_id;

INSERT INTO production_process_template_step (
  template_id, step_no, step_code, step_name,
  resource_kind, machine_type_id, hr_department_id, hr_work_type_id,
  setup_minutes, run_minutes_per_unit, remark, is_active
)
VALUES
  (@proc_tpl_id, 1, 'FF26_S1', 'FF26 Preparation', 'hr_work_type', 0, @work_type_id, @work_type_id, 10.00, 0.2000, 'FF26 step prep', 1),
  (@proc_tpl_id, 2, 'FF26_S2', 'FF26 Machining', 'machine_type', @machine_type_id, 0, 0, 20.00, 0.5000, 'FF26 step machine', 1),
  (@proc_tpl_id, 3, 'FF26_S3', 'FF26 Assembly', 'hr_work_type', 0, @work_type_id, @work_type_id, 10.00, 0.3000, 'FF26 step assembly', 1);

INSERT INTO production_product_routing (
  product_id, template_id, is_active, override_mode, remark, created_by
)
VALUES (
  @prod_id, @proc_tpl_id, 1, 'inherit', 'FF26 product routing', @admin_user_id
)
ON DUPLICATE KEY UPDATE
  template_id = VALUES(template_id),
  is_active = VALUES(is_active),
  override_mode = VALUES(override_mode),
  remark = VALUES(remark),
  created_by = COALESCE(production_product_routing.created_by, VALUES(created_by));

SET @routing_id := (
  SELECT id FROM production_product_routing
  WHERE product_id = @prod_id
  LIMIT 1
);

DELETE FROM production_product_routing_step WHERE routing_id = @routing_id;

-- ------------------------------------------------------------------
-- 4) Supplier/material mapping and procurement data
-- ------------------------------------------------------------------

INSERT INTO supplier (
  company_id, name, contact_name, phone, address, is_active, remark
)
VALUES
  (@company_id, 'FF26 Supplier A', 'FF26 SA Contact', '13800002611', 'FF26 Supplier Address A', 1, 'FF26 preferred supplier'),
  (@company_id, 'FF26 Supplier B', 'FF26 SB Contact', '13800002612', 'FF26 Supplier Address B', 1, 'FF26 backup supplier')
ON DUPLICATE KEY UPDATE
  contact_name = VALUES(contact_name),
  phone = VALUES(phone),
  address = VALUES(address),
  is_active = VALUES(is_active),
  remark = VALUES(remark);

SET @sup_a_id := (
  SELECT id FROM supplier
  WHERE company_id = @company_id AND name = 'FF26 Supplier A'
  LIMIT 1
);
SET @sup_b_id := (
  SELECT id FROM supplier
  WHERE company_id = @company_id AND name = 'FF26 Supplier B'
  LIMIT 1
);

INSERT INTO supplier_material_map (
  company_id, supplier_id, material_id, is_preferred, is_active, last_unit_price, remark
)
VALUES
  (@company_id, @sup_a_id, @mat_a_id, 1, 1, 8.80, 'FF26 preferred mapping raw A'),
  (@company_id, @sup_b_id, @mat_a_id, 0, 1, 9.20, 'FF26 backup mapping raw A'),
  (@company_id, @sup_a_id, @mat_b_id, 1, 1, 4.50, 'FF26 preferred mapping raw B'),
  (@company_id, @sup_a_id, @mat_done_id, 1, 1, 6.00, 'FF26 preferred mapping done sample')
ON DUPLICATE KEY UPDATE
  company_id = VALUES(company_id),
  is_preferred = VALUES(is_preferred),
  is_active = VALUES(is_active),
  last_unit_price = VALUES(last_unit_price),
  remark = VALUES(remark);

-- ------------------------------------------------------------------
-- 5) Pending chain data: sales order + requisition (for manual experience)
-- ------------------------------------------------------------------

INSERT INTO sales_order (
  order_no, customer_order_no, customer_id, salesperson,
  order_date, required_date, status, payment_type, remark
)
VALUES (
  'FF26_SO_TODO_001', 'FF26-CO-TODO-001', @cust_id, 'FF26_SALES',
  @today, DATE_ADD(@today, INTERVAL 7 DAY), 'pending', 'monthly', 'FF26 pending order for full-flow manual test'
)
ON DUPLICATE KEY UPDATE
  customer_order_no = VALUES(customer_order_no),
  customer_id = VALUES(customer_id),
  salesperson = VALUES(salesperson),
  order_date = VALUES(order_date),
  required_date = VALUES(required_date),
  status = VALUES(status),
  payment_type = VALUES(payment_type),
  remark = VALUES(remark);

SET @so_todo_id := (SELECT id FROM sales_order WHERE order_no = 'FF26_SO_TODO_001' LIMIT 1);

SET @oi_todo_id := (
  SELECT id FROM order_item
  WHERE order_id = @so_todo_id AND customer_product_id = @cp_id
  ORDER BY id DESC
  LIMIT 1
);

INSERT INTO order_item (
  order_id, customer_product_id, product_name, product_spec,
  customer_material_no, quantity, unit, price, amount, is_sample
)
SELECT
  @so_todo_id,
  @cp_id,
  'FF26 Finished Product A',
  'FF26-SPEC-A',
  'FF26-CMAT-001',
  120.0000,
  'pcs',
  12.5000,
  1500.00,
  0
WHERE @oi_todo_id IS NULL;

SET @oi_todo_id := (
  SELECT id FROM order_item
  WHERE order_id = @so_todo_id AND customer_product_id = @cp_id
  ORDER BY id DESC
  LIMIT 1
);

UPDATE order_item
SET
  product_name = 'FF26 Finished Product A',
  product_spec = 'FF26-SPEC-A',
  customer_material_no = 'FF26-CMAT-001',
  quantity = 120.0000,
  unit = 'pcs',
  price = 12.5000,
  amount = 1500.00,
  is_sample = 0
WHERE id = @oi_todo_id;

INSERT INTO purchase_requisition (
  company_id, req_no, requester_user_id,
  supplier_name, item_name, item_spec,
  qty, unit, expected_date,
  status, printed_at, signed_at, signed_by, remark
)
VALUES (
  @company_id, 'FF26_REQ_TODO_001', @admin_user_id,
  'FF26 Supplier A', 'FF26 Raw Material A', 'FF26-MAT-A',
  120.00, 'kg', DATE_ADD(@today, INTERVAL 3 DAY),
  'signed', NULL, NOW(), @admin_user_id, 'FF26 pending requisition for manual order generation'
)
ON DUPLICATE KEY UPDATE
  requester_user_id = VALUES(requester_user_id),
  supplier_name = VALUES(supplier_name),
  item_name = VALUES(item_name),
  item_spec = VALUES(item_spec),
  qty = VALUES(qty),
  unit = VALUES(unit),
  expected_date = VALUES(expected_date),
  status = VALUES(status),
  signed_at = VALUES(signed_at),
  signed_by = VALUES(signed_by),
  remark = VALUES(remark);

SET @req_todo_id := (SELECT id FROM purchase_requisition WHERE req_no = 'FF26_REQ_TODO_001' LIMIT 1);

INSERT INTO purchase_requisition_line (
  company_id, requisition_id, line_no,
  supplier_id, material_id,
  supplier_name, item_name, item_spec,
  qty, unit, expected_date,
  status, remark
)
VALUES (
  @company_id, @req_todo_id, 1,
  @sup_a_id, @mat_a_id,
  'FF26 Supplier A', 'FF26 Raw Material A', 'FF26-MAT-A',
  120.00, 'kg', DATE_ADD(@today, INTERVAL 3 DAY),
  'pending_order', 'FF26 pending requisition line'
)
ON DUPLICATE KEY UPDATE
  supplier_id = VALUES(supplier_id),
  material_id = VALUES(material_id),
  supplier_name = VALUES(supplier_name),
  item_name = VALUES(item_name),
  item_spec = VALUES(item_spec),
  qty = VALUES(qty),
  unit = VALUES(unit),
  expected_date = VALUES(expected_date),
  status = VALUES(status),
  remark = VALUES(remark);

UPDATE purchase_requisition
SET
  supplier_name = 'FF26 Supplier A',
  item_name = 'FF26 Raw Material A',
  item_spec = 'FF26-MAT-A',
  qty = 120.00,
  unit = 'kg',
  status = 'signed',
  signed_at = COALESCE(signed_at, NOW()),
  signed_by = COALESCE(signed_by, @admin_user_id)
WHERE id = @req_todo_id;

-- ------------------------------------------------------------------
-- 6) Done chain data: requisition -> PO -> receipt -> stock-in -> inventory
-- ------------------------------------------------------------------

INSERT INTO purchase_requisition (
  company_id, req_no, requester_user_id,
  supplier_name, item_name, item_spec,
  qty, unit, expected_date,
  status, printed_at, signed_at, signed_by, remark
)
VALUES (
  @company_id, 'FF26_REQ_DONE_001', @admin_user_id,
  'FF26 Supplier A', 'FF26 Raw Material Done Sample', 'FF26-MAT-DONE',
  80.00, 'kg', DATE_ADD(@today, INTERVAL 1 DAY),
  'ordered', NOW(), NOW(), @admin_user_id, 'FF26 completed requisition sample'
)
ON DUPLICATE KEY UPDATE
  requester_user_id = VALUES(requester_user_id),
  supplier_name = VALUES(supplier_name),
  item_name = VALUES(item_name),
  item_spec = VALUES(item_spec),
  qty = VALUES(qty),
  unit = VALUES(unit),
  expected_date = VALUES(expected_date),
  status = VALUES(status),
  printed_at = VALUES(printed_at),
  signed_at = VALUES(signed_at),
  signed_by = VALUES(signed_by),
  remark = VALUES(remark);

SET @req_done_id := (SELECT id FROM purchase_requisition WHERE req_no = 'FF26_REQ_DONE_001' LIMIT 1);

INSERT INTO purchase_requisition_line (
  company_id, requisition_id, line_no,
  supplier_id, material_id,
  supplier_name, item_name, item_spec,
  qty, unit, expected_date,
  status, remark
)
VALUES (
  @company_id, @req_done_id, 1,
  @sup_a_id, @mat_done_id,
  'FF26 Supplier A', 'FF26 Raw Material Done Sample', 'FF26-MAT-DONE',
  80.00, 'kg', DATE_ADD(@today, INTERVAL 1 DAY),
  'ordered', 'FF26 completed requisition line'
)
ON DUPLICATE KEY UPDATE
  supplier_id = VALUES(supplier_id),
  material_id = VALUES(material_id),
  supplier_name = VALUES(supplier_name),
  item_name = VALUES(item_name),
  item_spec = VALUES(item_spec),
  qty = VALUES(qty),
  unit = VALUES(unit),
  expected_date = VALUES(expected_date),
  status = VALUES(status),
  remark = VALUES(remark);

SET @req_done_line_id := (
  SELECT id FROM purchase_requisition_line
  WHERE requisition_id = @req_done_id AND line_no = 1
  LIMIT 1
);

INSERT INTO purchase_order (
  company_id, po_no,
  requisition_id, requisition_line_id,
  buyer_user_id,
  supplier_id, material_id,
  supplier_name, supplier_contact_name, supplier_phone, supplier_address,
  item_name, item_spec,
  qty, unit, unit_price, amount,
  expected_date,
  status, ordered_at, ordered_by,
  printed_at,
  reconcile_status,
  remark
)
VALUES (
  @company_id, 'FF26_PO_DONE_001',
  @req_done_id, @req_done_line_id,
  @admin_user_id,
  @sup_a_id, @mat_done_id,
  'FF26 Supplier A', 'FF26 SA Contact', '13800002611', 'FF26 Supplier Address A',
  'FF26 Raw Material Done Sample', 'FF26-MAT-DONE',
  80.00, 'kg', 6.00, 480.00,
  DATE_ADD(@today, INTERVAL 1 DAY),
  'received', NOW(), @admin_user_id,
  NOW(),
  'matched',
  'FF26 completed purchase order sample'
)
ON DUPLICATE KEY UPDATE
  company_id = VALUES(company_id),
  requisition_id = VALUES(requisition_id),
  requisition_line_id = VALUES(requisition_line_id),
  buyer_user_id = VALUES(buyer_user_id),
  supplier_id = VALUES(supplier_id),
  material_id = VALUES(material_id),
  supplier_name = VALUES(supplier_name),
  supplier_contact_name = VALUES(supplier_contact_name),
  supplier_phone = VALUES(supplier_phone),
  supplier_address = VALUES(supplier_address),
  item_name = VALUES(item_name),
  item_spec = VALUES(item_spec),
  qty = VALUES(qty),
  unit = VALUES(unit),
  unit_price = VALUES(unit_price),
  amount = VALUES(amount),
  expected_date = VALUES(expected_date),
  status = VALUES(status),
  ordered_at = VALUES(ordered_at),
  ordered_by = VALUES(ordered_by),
  printed_at = VALUES(printed_at),
  reconcile_status = VALUES(reconcile_status),
  remark = VALUES(remark);

SET @po_done_id := (SELECT id FROM purchase_order WHERE po_no = 'FF26_PO_DONE_001' LIMIT 1);

INSERT INTO purchase_receipt (
  company_id, receipt_no, purchase_order_id,
  receiver_user_id,
  received_qty, received_at,
  status,
  reconcile_status, reconcile_note, reconciled_at, reconciled_by,
  remark
)
VALUES (
  @company_id, 'FF26_RCV_DONE_001', @po_done_id,
  @admin_user_id,
  80.00, NOW(),
  'posted',
  'matched', 'FF26 matched sample', NOW(), @admin_user_id,
  'FF26 completed receipt sample'
)
ON DUPLICATE KEY UPDATE
  company_id = VALUES(company_id),
  purchase_order_id = VALUES(purchase_order_id),
  receiver_user_id = VALUES(receiver_user_id),
  received_qty = VALUES(received_qty),
  received_at = VALUES(received_at),
  status = VALUES(status),
  reconcile_status = VALUES(reconcile_status),
  reconcile_note = VALUES(reconcile_note),
  reconciled_at = VALUES(reconciled_at),
  reconciled_by = VALUES(reconciled_by),
  remark = VALUES(remark);

SET @rcv_done_id := (SELECT id FROM purchase_receipt WHERE receipt_no = 'FF26_RCV_DONE_001' LIMIT 1);

INSERT INTO purchase_stock_in (
  company_id, stock_in_no,
  receipt_id, purchase_order_id,
  qty, received_qty, warehouse_qty, variance_qty,
  approval_status,
  storage_area,
  stock_in_at,
  created_by,
  approved_by, approved_at,
  remark
)
VALUES (
  @company_id, 'FF26_SIN_DONE_001',
  @rcv_done_id, @po_done_id,
  80.00, 80.00, 80.00, 0.00,
  'matched',
  'FF26_A01',
  NOW(),
  @admin_user_id,
  @admin_user_id, NOW(),
  'FF26 completed stock-in sample'
)
ON DUPLICATE KEY UPDATE
  company_id = VALUES(company_id),
  receipt_id = VALUES(receipt_id),
  purchase_order_id = VALUES(purchase_order_id),
  qty = VALUES(qty),
  received_qty = VALUES(received_qty),
  warehouse_qty = VALUES(warehouse_qty),
  variance_qty = VALUES(variance_qty),
  approval_status = VALUES(approval_status),
  storage_area = VALUES(storage_area),
  stock_in_at = VALUES(stock_in_at),
  created_by = VALUES(created_by),
  approved_by = VALUES(approved_by),
  approved_at = VALUES(approved_at),
  remark = VALUES(remark);

INSERT INTO inventory_opening_balance (
  category, product_id, material_id, storage_area, opening_qty, unit, remark
)
VALUES (
  'material', 0, @mat_done_id, 'FF26_A01', 0.0000, 'kg', 'FF26 done sample opening balance'
)
ON DUPLICATE KEY UPDATE
  unit = VALUES(unit),
  remark = VALUES(remark);

INSERT INTO inventory_movement (
  category, direction,
  product_id, material_id,
  storage_area,
  quantity, unit,
  biz_date,
  source_type,
  source_delivery_id, source_delivery_item_id,
  source_purchase_order_id, source_purchase_receipt_id,
  remark,
  created_by,
  movement_batch_id
)
SELECT
  'material', 'in',
  0, @mat_done_id,
  'FF26_A01',
  80.0000, 'kg',
  @today,
  'procurement',
  NULL, NULL,
  @po_done_id, @rcv_done_id,
  'FF26 completed procurement in movement',
  @admin_user_id,
  NULL
WHERE NOT EXISTS (
  SELECT 1
  FROM inventory_movement m
  WHERE m.category = 'material'
    AND m.direction = 'in'
    AND m.material_id = @mat_done_id
    AND m.source_purchase_order_id = @po_done_id
    AND m.source_purchase_receipt_id = @rcv_done_id
);

UPDATE purchase_order
SET status = 'received', reconcile_status = 'matched'
WHERE id = @po_done_id;

UPDATE purchase_receipt
SET status = 'posted', reconcile_status = 'matched', reconciled_at = COALESCE(reconciled_at, NOW()), reconciled_by = COALESCE(reconciled_by, @admin_user_id)
WHERE id = @rcv_done_id;

UPDATE purchase_requisition
SET status = 'ordered', signed_at = COALESCE(signed_at, NOW()), signed_by = COALESCE(signed_by, @admin_user_id)
WHERE id = @req_done_id;

UPDATE purchase_requisition_line
SET status = 'ordered'
WHERE id = @req_done_line_id;

-- ------------------------------------------------------------------
-- 7) Optional convenience preplan (draft) for quick measure click path
-- ------------------------------------------------------------------

SET @preplan_todo_id := (
  SELECT id FROM production_preplan
  WHERE source_type = 'manual' AND customer_id = @cust_id AND remark = 'FF26_PREPLAN_TODO'
  ORDER BY id ASC
  LIMIT 1
);

INSERT INTO production_preplan (
  source_type, plan_date, customer_id, status, remark, created_by
)
SELECT
  'manual', @today, @cust_id, 'draft', 'FF26_PREPLAN_TODO', @admin_user_id
WHERE @preplan_todo_id IS NULL;

SET @preplan_todo_id := (
  SELECT id FROM production_preplan
  WHERE source_type = 'manual' AND customer_id = @cust_id AND remark = 'FF26_PREPLAN_TODO'
  ORDER BY id ASC
  LIMIT 1
);

INSERT INTO production_preplan_line (
  preplan_id, line_no, source_type, source_order_item_id, product_id, quantity, unit, remark
)
VALUES (
  @preplan_todo_id, 1, 'manual', NULL, @prod_id, 120.0000, 'pcs', 'FF26 preplan line'
)
ON DUPLICATE KEY UPDATE
  source_type = VALUES(source_type),
  source_order_item_id = VALUES(source_order_item_id),
  product_id = VALUES(product_id),
  quantity = VALUES(quantity),
  unit = VALUES(unit),
  remark = VALUES(remark);

UPDATE production_preplan
SET plan_date = @today, status = 'draft', remark = 'FF26_PREPLAN_TODO', created_by = COALESCE(created_by, @admin_user_id)
WHERE id = @preplan_todo_id;

-- End of seed
