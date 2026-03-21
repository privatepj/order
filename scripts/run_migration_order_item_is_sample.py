import pymysql


def main() -> None:
    conn = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="as45as45",
        database="sydixon_order",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "ALTER TABLE `order_item` "
                    "ADD COLUMN `is_sample` TINYINT(1) NOT NULL DEFAULT 0 AFTER `amount`"
                )
                print("OK: added column order_item.is_sample")
            except Exception as e:
                print("WARN: alter table skipped:", e)

            cur.execute(
                "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='order_item' AND COLUMN_NAME='is_sample'",
                ("sydixon_order",),
            )
            rows = cur.fetchall()
            print("CHECK: is_sample column =", rows)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

