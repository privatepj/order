"""在本地执行 scripts/sql/00_full_schema.sql（会 DROP 并重建所有表，清空数据）。

读取项目根 .env 中的 DATABASE_URL，连接到其中的数据库后执行整份 SQL。
依赖 PyMySQL 的 CLIENT.MULTI_STATEMENTS，适用于未安装 mysql 客户端的 Windows。

用法:
  python scripts/run_full_schema.py
  python scripts/run_full_schema.py --yes   # 跳过确认（CI/自动化）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

import pymysql
from pymysql.constants import CLIENT

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
SQL_FILE = ROOT / "scripts" / "sql" / "00_full_schema.sql"


def _parse_database_url() -> tuple[str, str, str, str, int]:
    if not ENV.is_file():
        print("未找到 .env，请复制 .env.example 为 .env 并填写 DATABASE_URL。", file=sys.stderr)
        sys.exit(1)
    raw = ENV.read_text(encoding="utf-8")
    m = re.search(r"^DATABASE_URL=(.+)$", raw, re.M)
    if not m:
        print(".env 中无 DATABASE_URL。", file=sys.stderr)
        sys.exit(1)
    url = m.group(1).strip().strip('"').strip("'")
    p = urlparse(url.replace("mysql+pymysql", "mysql"))
    db = (p.path or "").lstrip("/") or "sydixon_order"
    user = unquote(p.username or "root")
    password = unquote(p.password or "")
    host = p.hostname or "localhost"
    port = int(p.port or 3306)
    return host, port, user, password, db


def main() -> int:
    parser = argparse.ArgumentParser(description="执行 00_full_schema.sql（清空并重建库）")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="不询问确认，直接执行",
    )
    args = parser.parse_args()

    if not SQL_FILE.is_file():
        print(f"未找到: {SQL_FILE}", file=sys.stderr)
        return 1

    host, port, user, password, db = _parse_database_url()

    if not args.yes:
        print("警告: 本操作将 DROP 并重建 sydixon_order 内业务表，当前库内数据会全部丢失。")
        print(f"目标: {host}:{port} 数据库 `{db}`")
        ans = input("确认继续请输入 YES: ").strip()
        if ans != "YES":
            print("已取消。")
            return 1

    sql_text = SQL_FILE.read_text(encoding="utf-8")

    print(f"连接 {host}:{port}，数据库 `{db}` …")
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        connect_timeout=30,
        client_flag=CLIENT.MULTI_STATEMENTS,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql_text)
            while cur.nextset():
                pass
    except pymysql.Error as e:
        print(f"MySQL 错误: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print("00_full_schema.sql 已执行完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
