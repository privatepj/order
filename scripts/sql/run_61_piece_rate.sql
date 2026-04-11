USE sydixon_order;
SET NAMES utf8mb4;

-- 工种计件单价表
CREATE TABLE IF NOT EXISTS `hr_department_piece_rate` (
  `id`               int NOT NULL AUTO_INCREMENT,
  `company_id`       int NOT NULL,
  `hr_department_id` int NOT NULL,
  `period`           varchar(7) NOT NULL COMMENT 'YYYY-MM',
  `rate_per_unit`    decimal(14,4) NOT NULL DEFAULT 0.0000 COMMENT '元/件',
  `remark`           varchar(500) DEFAULT NULL,
  `created_by`       int NOT NULL,
  `created_at`       datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dept_period` (`company_id`,`hr_department_id`,`period`),
  KEY `idx_company_period` (`company_id`,`period`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
