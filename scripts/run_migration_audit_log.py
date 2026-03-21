"""创建 audit_log 表及索引（可重复执行）。"""
import pymysql


def main():
    conn = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="as45as45",
        database="sydixon_order",
        autocommit=True,
    )
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS `audit_log` (
          `id` BIGINT NOT NULL AUTO_INCREMENT,
          `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
          `event_type` VARCHAR(16) NOT NULL,
          `method` VARCHAR(8) NULL,
          `path` VARCHAR(512) NOT NULL,
          `query_string` VARCHAR(2048) NULL,
          `status_code` SMALLINT NULL,
          `duration_ms` INT NULL,
          `user_id` INT NULL,
          `auth_type` VARCHAR(16) NOT NULL,
          `ip` VARCHAR(45) NOT NULL,
          `user_agent` VARCHAR(512) NULL,
          `endpoint` VARCHAR(128) NULL,
          `extra` JSON NULL,
          PRIMARY KEY (`id`),
          KEY `ix_audit_log_created_at` (`created_at`),
          KEY `ix_audit_log_user_created` (`user_id`, `created_at`),
          KEY `ix_audit_log_path` (`path`(191))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    print("OK: audit_log table")
    cur.close()
    conn.close()
    print("done")


if __name__ == "__main__":
    main()
