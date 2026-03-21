"""Execute migrate_company_order_no against DB (same as mcp mysql_sydixon_order)."""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL", "")
# mysql+pymysql://user:pass@host:port/db
if "mysql" in url and "@" in url:
    rest = url.split("mysql+pymysql://", 1)[-1].split("@")
    user_part, host_part = rest[0], rest[1]
    if ":" in user_part:
        user, password = user_part.split(":", 1)
    else:
        user, password = user_part, ""
    hp, db = host_part.rsplit("/", 1)
    if ":" in hp:
        host, port = hp.split(":")
        port = int(port)
    else:
        host, port = hp, 3306
else:
    host, port, user, password = "127.0.0.1", 3306, "root", "as45as45"

conn = pymysql.connect(
    host=host, port=port, user=user, password=password, database="sydixon_order", charset="utf8mb4"
)
cur = conn.cursor()
alter_sql = """
ALTER TABLE company
  ADD COLUMN order_no_prefix varchar(32) DEFAULT NULL COMMENT 'order prefix' AFTER code,
  ADD COLUMN billing_cycle_day tinyint unsigned NOT NULL DEFAULT 1 COMMENT 'billing day' AFTER order_no_prefix
"""
try:
    cur.execute(alter_sql)
    conn.commit()
    print("ALTER: OK")
except Exception as e:
    err = str(e)
    if "1060" in err or "Duplicate column" in err:
        print("ALTER: skipped (columns exist)")
    else:
        conn.rollback()
        raise

cur.execute(
    "UPDATE company SET order_no_prefix = code WHERE order_no_prefix IS NULL OR order_no_prefix = ''"
)
conn.commit()
print("UPDATE rows:", cur.rowcount)
conn.close()
print("Done.")
