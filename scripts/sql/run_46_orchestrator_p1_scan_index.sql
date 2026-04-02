-- P1: overdue scan performance index
-- append-only migration; no foreign keys

USE sydixon_order;
SET NAMES utf8mb4;

ALTER TABLE `sales_order`
  ADD KEY `idx_sales_order_required_status` (`required_date`, `status`);
