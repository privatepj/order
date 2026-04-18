-- 移除主数据「类型」列（nav_type），统一使用「系列」（series）
ALTER TABLE `product` DROP COLUMN `nav_type`;
ALTER TABLE `semi_material` DROP COLUMN `nav_type`;
