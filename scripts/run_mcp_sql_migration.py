"""使用 .cursor/mcp.json 中 mysql_sydixon_order 的配置执行 run_14_role_capability_keys.sql。"""
import json
import re
import sys
from pathlib import Path

import pymysql
from pymysql.err import OperationalError

ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / ".cursor" / "mcp.json"
SQL_FILE = ROOT / "scripts" / "sql" / "run_14_role_capability_keys.sql"


def main():
    cfg = json.loads(MCP.read_text(encoding="utf-8"))
    e = cfg["mcpServers"]["mysql_sydixon_order"]["env"]
    conn = pymysql.connect(
        host=e["MYSQL_HOST"],
        port=int(e["MYSQL_PORT"]),
        user=e["MYSQL_USER"],
        password=e["MYSQL_PASS"],
        database=e["MYSQL_DB"],
        charset="utf8mb4",
    )
    raw = SQL_FILE.read_text(encoding="utf-8")
    m = re.search(r"ALTER\s+TABLE[^;]+;", raw, re.IGNORECASE | re.DOTALL)
    if not m:
        print("失败: SQL 文件中未找到 ALTER TABLE", file=sys.stderr)
        sys.exit(1)
    stmt = m.group(0).rstrip().rstrip(";").strip()
    cur = conn.cursor()
    try:
        cur.execute(stmt)
        conn.commit()
        print("OK: allowed_capability_keys added (%s)" % e["MYSQL_DB"])
    except OperationalError as ex:
        if ex.args[0] == 1060:
            print("Skip: column allowed_capability_keys already exists")
            conn.rollback()
        else:
            conn.rollback()
            raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print("Error:", err, file=sys.stderr)
        sys.exit(1)
