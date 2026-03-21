"""一次性执行 order_item.is_sample、customer.short_code 迁移。"""
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
    stmts = [
        ("order_item.is_sample", "ALTER TABLE `order_item` ADD COLUMN `is_sample` TINYINT(1) NOT NULL DEFAULT 0 AFTER `amount`"),
        ("customer.short_code", "ALTER TABLE `customer` ADD COLUMN `short_code` VARCHAR(32) NULL AFTER `customer_code`"),
    ]
    for name, sql in stmts:
        try:
            cur.execute(sql)
            print("OK:", name)
        except Exception as e:
            err = str(e)
            if "1060" in err or "Duplicate column" in err:
                print("SKIP (exists):", name)
            else:
                print("ERR:", name, e)
    cur.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='order_item' AND COLUMN_NAME='is_sample'",
        ("sydixon_order",),
    )
    print("check is_sample:", cur.fetchone())
    cur.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='customer' AND COLUMN_NAME='short_code'",
        ("sydixon_order",),
    )
    print("check short_code:", cur.fetchone())
    cur.close()
    conn.close()
    print("done")

if __name__ == "__main__":
    main()
