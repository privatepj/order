-- 主数据内部分类/导航（非成品-半成品体系）：product / semi_material

ALTER TABLE `product`
  ADD COLUMN `nav_type` varchar(64) DEFAULT NULL COMMENT '主数据内部分类/导航' AFTER `series`;

ALTER TABLE `semi_material`
  ADD COLUMN `nav_type` varchar(64) DEFAULT NULL COMMENT '主数据内部分类/导航' AFTER `series`;
