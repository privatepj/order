"""对账导出相关列：逐列 ADD，已存在则跳过。"""
import os

import pymysql
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL", "")
if "mysql" in url and "@" in url:
    rest = url.split("mysql+pymysql://", 1)[-1].split("@")
    user_part, host_part = rest[0], rest[1]
    if ":" in user_part:
        user, password = user_part.split(":", 1)
    else:
        user, password = user_part, ""
    hp, db = host_part.rsplit("/", 1)
    if ":" in hp:
        host, port = hp.split(":", 1)
        port = int(port)
    else:
        host, port = hp, 3306
else:
    host, port, user, password = "127.0.0.1", 3306, "root", "as45as45"
    db = "sydixon_order"

conn = pymysql.connect(
    host=host, port=port, user=user, password=password, database=db, charset="utf8mb4"
)
cur = conn.cursor()

company_cols = [
    ("phone", "varchar(32) DEFAULT NULL COMMENT '电话'"),
    ("fax", "varchar(32) DEFAULT NULL COMMENT '传真'"),
    ("address", "varchar(255) DEFAULT NULL COMMENT '地址'"),
    ("contact_person", "varchar(64) DEFAULT NULL COMMENT '联系人'"),
    ("private_account", "varchar(64) DEFAULT NULL COMMENT '对私账户'"),
    ("public_account", "varchar(64) DEFAULT NULL COMMENT '对公账户'"),
    ("account_name", "varchar(64) DEFAULT NULL COMMENT '户名'"),
    ("bank_name", "varchar(128) DEFAULT NULL COMMENT '开户行'"),
    ("preparer_name", "varchar(64) DEFAULT NULL COMMENT '对账制表人'"),
]

after = "billing_cycle_day"
for col, defn in company_cols:
    try:
        cur.execute(f"ALTER TABLE company ADD COLUMN `{col}` {defn} AFTER `{after}`")
        conn.commit()
        print(f"company.{col}: OK")
        after = col
    except Exception as e:
        err = str(e)
        if "1060" in err or "Duplicate column" in err:
            print(f"company.{col}: skip")
            conn.rollback()
        else:
            conn.rollback()
            raise

# customer.fax after phone
try:
    cur.execute(
        "ALTER TABLE customer ADD COLUMN fax varchar(32) DEFAULT NULL COMMENT '传真' AFTER phone"
    )
    conn.commit()
    print("customer.fax: OK")
except Exception as e:
    err = str(e)
    if "1060" in err or "Duplicate column" in err:
        print("customer.fax: skip")
        conn.rollback()
    else:
        conn.rollback()
        raise

conn.close()
print("Done.")
