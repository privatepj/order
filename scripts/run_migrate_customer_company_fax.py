"""补齐 customer.fax、company 联系/账户等列（列已存在则跳过）。"""
import os
import pathlib
import re

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
        host, port = hp.split(":")
        port = int(port)
    else:
        host, port = hp, 3306
else:
    host, port, user, password = "127.0.0.1", 3306, "root", ""
    db = "sydixon_order"

sql_path = pathlib.Path(__file__).resolve().parent / "migrate_customer_company_fax.sql"
text = sql_path.read_text(encoding="utf8")
stmts = [
    m.group(0).strip().rstrip(";")
    for m in re.finditer(r"ALTER\s+TABLE[^;]+;", text, re.IGNORECASE | re.DOTALL)
]

conn = pymysql.connect(
    host=host, port=port, user=user, password=password, database=db, charset="utf8mb4"
)
try:
    for stmt in stmts:
        try:
            with conn.cursor() as cur:
                cur.execute(stmt)
            conn.commit()
            print("OK:", stmt[:70], "...")
        except Exception as e:
            err = str(e)
            if "1060" in err or "Duplicate column" in err:
                print("skip (exists):", stmt[:60], "...")
            else:
                raise
finally:
    conn.close()
