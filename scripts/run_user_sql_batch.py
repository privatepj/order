"""执行 scripts/sql/user_today/ 下的用户脚本（按 sha256 跳过已执行脚本）。

使用方式：
1) 把今天新增/改动的 SQL 放入 scripts/sql/user_today/ （按需可一次放多个）
2) python scripts/run_user_sql_batch.py

去重依据：
- 计算每个脚本的 sha256（按文件内容），写入 sql_user_script_run_log
- 若 sha 已存在则跳过（允许同名但内容变更时重新执行）
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

import pymysql


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
USER_DIR = ROOT / "scripts" / "sql" / "user_today"


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_sql_statements(script_text: str) -> Iterable[str]:
    # 兼容 run_sql_file.py：剔除 USE ...; 并按 ';' 粗分割
    lines = [
        ln for ln in script_text.splitlines() if not ln.strip().upper().startswith("USE ")
    ]
    script = "\n".join(lines)

    for stmt in script.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        if all(
            not x.strip() or x.strip().startswith("--") for x in stmt.splitlines()
        ):
            continue
        yield stmt


def _ensure_run_log_table(cur) -> None:
    # 无外键约束；纯记录表，用于脚本去重。
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sql_user_script_run_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            script_filename VARCHAR(255) NOT NULL,
            script_sha256 CHAR(64) NOT NULL UNIQUE,
            executed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    )


def _already_ran(cur, sha: str) -> bool:
    cur.execute(
        "SELECT id FROM sql_user_script_run_log WHERE script_sha256=%s LIMIT 1",
        (sha,),
    )
    return cur.fetchone() is not None


def _mark_ran(cur, filename: str, sha: str) -> None:
    cur.execute(
        """
        INSERT INTO sql_user_script_run_log (script_filename, script_sha256, executed_at)
        VALUES (%s, %s, NOW())
        """,
        (filename, sha),
    )


def main() -> int:
    if not USER_DIR.is_dir():
        print(f"未找到用户脚本目录：{USER_DIR}")
        return 0

    sql_files = sorted([p for p in USER_DIR.iterdir() if p.is_file() and p.suffix == ".sql"])
    if not sql_files:
        print(f"{USER_DIR} 下无 .sql 文件，跳过。")
        return 0

    if not ENV.is_file():
        print("未找到 .env", file=sys.stderr)
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
    port = int(p.port or 3306)

    print(f"连接 {host}:{port} 数据库 {db} ...")
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
        _ensure_run_log_table(cur)
        conn.commit()

        ran_any = False
        for sql_path in sql_files:
            sha = _sha256_of_file(sql_path)
            if _already_ran(cur, sha):
                print(f"Skip: {sql_path.name} (already ran)")
                continue

            print(f"Execute: {sql_path.name}")
            text = sql_path.read_text(encoding="utf-8")

            try:
                for stmt in _iter_sql_statements(text):
                    cur.execute(stmt)
                _mark_ran(cur, sql_path.name, sha)
                conn.commit()
                ran_any = True
            except Exception as e:
                conn.rollback()
                print(f"ERR: 执行 {sql_path.name} 失败：{e}", file=sys.stderr)
                raise

        if not ran_any:
            print("本目录下所有脚本均已执行过，未发生任何操作。")

        cur.close()
    finally:
        conn.close()

    print("完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

