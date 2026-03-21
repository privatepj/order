"""执行 migrate_payment_type.sql（列已存在则跳过）。"""
import os
import pathlib

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

sql_path = pathlib.Path(__file__).resolve().parent / "migrate_payment_type.sql"
sql = sql_path.read_text(encoding="utf-8")
# 仅执行 ALTER 段
for stmt in sql.split(";"):
    stmt = stmt.strip()
    if not stmt.upper().startswith("ALTER"):
        continue
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
    )
    cur = conn.cursor()
    try:
        cur.execute(stmt)
        conn.commit()
        print("payment_type: OK")
    except Exception as e:
        err = str(e)
        if "1060" in err or "Duplicate column" in err:
            print("payment_type: already exists, skip")
        else:
            raise
    finally:
        conn.close()
    break
