"""对当前 .env 中的 DATABASE_URL 执行 run_87（若列已存在则跳过）。"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote_plus


def load_env():
    p = Path(__file__).resolve().parent.parent / ".env"
    if not p.exists():
        print("错误：未找到 .env", file=sys.stderr)
        sys.exit(1)
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        os.environ.setdefault(k, v)


def main():
    load_env()
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("错误：DATABASE_URL 未设置", file=sys.stderr)
        sys.exit(1)
    url = re.sub(r"^mysql\+pymysql", "mysql", url, count=1)
    parsed = urlparse(url)
    user = unquote_plus(parsed.username or "root")
    password = unquote_plus(parsed.password or "")
    host = parsed.hostname or "localhost"
    port = parsed.port or 3306
    db = (parsed.path or "/").lstrip("/").split("?")[0]

    import pymysql

    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
    )
    cur = conn.cursor()

    def has_col(table: str, col: str) -> bool:
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
            """,
            (db, table, col),
        )
        return cur.fetchone()[0] > 0

    print(f"目标库: {db} @ {host}:{port}")
    print(f"  product.nav_type 存在: {has_col('product', 'nav_type')}")
    print(f"  semi_material.nav_type 存在: {has_col('semi_material', 'nav_type')}")

    sql_path = Path(__file__).resolve().parent.parent / "scripts/sql/run_87_product_semi_nav_type.sql"
    sql = sql_path.read_text(encoding="utf-8")
    for part in sql.split(";"):
        stmt = part.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            cur.execute(stmt)
            conn.commit()
            print("已执行:", stmt.splitlines()[0][:70], "...")
        except Exception as e:
            conn.rollback()
            err = str(e)
            if "Duplicate column name" in err or "1060" in err:
                print("已跳过（列已存在）:", stmt.splitlines()[0][:50])
            else:
                print("执行失败:", e, file=sys.stderr)
                sys.exit(2)

    ok_p = has_col("product", "nav_type")
    ok_s = has_col("semi_material", "nav_type")
    print(f"校验: product.nav_type={ok_p}, semi_material.nav_type={ok_s}")
    if not (ok_p and ok_s):
        print("错误：迁移后仍缺少列", file=sys.stderr)
        sys.exit(3)
    print("完成：run_87 已就绪。")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
