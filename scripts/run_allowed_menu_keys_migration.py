"""一次性迁移：为 role 表增加 allowed_menu_keys（与 mcp.json / 生产库一致时可改连接参数）。"""
import pymysql

CONN = dict(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="as45as45",
    database="sydixon_order",
    charset="utf8mb4",
)

ALTER_SQL = """
ALTER TABLE `role`
  ADD COLUMN `allowed_menu_keys` json DEFAULT NULL COMMENT '可访问菜单 key 的 JSON 数组' AFTER `description`
"""

JSON_BUSINESS = '["order","delivery","customer","product","customer_product","reconciliation"]'


def main():
    conn = pymysql.connect(**CONN)
    try:
        cur = conn.cursor()
        try:
            cur.execute(ALTER_SQL)
            conn.commit()
            print("ALTER TABLE role ADD allowed_menu_keys: OK")
        except pymysql.err.OperationalError as e:
            if e.args[0] == 1060:
                print("Column allowed_menu_keys already exists, skip ALTER")
                conn.rollback()
            else:
                raise

        cur.execute(
            """
            UPDATE `role` SET `allowed_menu_keys` = CAST(%s AS JSON)
            WHERE `code` IN ('sales', 'warehouse', 'finance')
            """,
            (JSON_BUSINESS,),
        )
        print("UPDATE sales/warehouse/finance rows:", cur.rowcount)

        cur.execute(
            "UPDATE `role` SET `allowed_menu_keys` = CAST(%s AS JSON) WHERE `code` = 'pending'",
            ("[]",),
        )
        print("UPDATE pending rows:", cur.rowcount)

        conn.commit()
        cur.close()
    finally:
        conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
