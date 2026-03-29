"""执行 scripts/sql/ 下指定 SQL 文件（读项目根 .env 的 DATABASE_URL）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

import pymysql

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/run_sql_file.py scripts/sql/run_22_....sql", file=sys.stderr)
        return 1
    sql_path = Path(sys.argv[1])
    if not sql_path.is_absolute():
        sql_path = ROOT / sql_path
    if not ENV.is_file():
        print("未找到 .env", file=sys.stderr)
        return 1
    if not sql_path.is_file():
        print(f"未找到 SQL 文件: {sql_path}", file=sys.stderr)
        return 1
    raw = ENV.read_text(encoding="utf-8")
    m = re.search(r"^DATABASE_URL=(.+)$", raw, re.M)
    if not m:
        print(".env 中无 DATABASE_URL", file=sys.stderr)
        return 1
    url = m.group(1).strip().strip('"').strip("'")
    p = urlparse(url.replace("mysql+pymysql", "mysql"))
    db = p.path.lstrip("/") or "sydixon_order"
    user = unquote(p.username or "root")
    password = unquote(p.password or "")
    host = p.hostname or "localhost"
    port = p.port or 3306

    text = sql_path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not ln.strip().upper().startswith("USE ")]
    script = "\n".join(lines)

    print(f"连接 {host}:{port} 数据库 {db} …")
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        connect_timeout=10,
    )
    try:
        cur = conn.cursor()
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue
            if all(
                not x.strip() or x.strip().startswith("--")
                for x in stmt.splitlines()
            ):
                continue
            cur.execute(stmt)
            first = next(
                (x for x in stmt.splitlines() if x.strip() and not x.strip().startswith("--")),
                stmt,
            )
            print("OK:", first[:100])
        conn.commit()
        cur.close()
    finally:
        conn.close()
    print("完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
