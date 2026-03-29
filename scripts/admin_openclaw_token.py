"""从 mcp.json 读库，为 admin 管理 OpenClaw API 令牌（仅存哈希；需新生成明文时撤销旧有效令牌后插入）。"""
import json
import hashlib
import secrets
import sys
from pathlib import Path

import pymysql


def load_mysql_env():
    for p in [
        Path(r"C:/Users/高高/.cursor/mcp.json"),
        Path(__file__).resolve().parents[1] / ".cursor" / "mcp.json",
    ]:
        if not p.exists():
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        for srv in (j.get("mcpServers") or {}).values():
            if isinstance(srv, dict):
                e = srv.get("env") or {}
                if e.get("MYSQL_DB") and e.get("MYSQL_USER") is not None:
                    return e
    sys.exit("未找到含 MYSQL_* 的 mcp.json（全局 ~/.cursor/mcp.json 为空时请配置项目 .cursor/mcp.json）")


def main():
    only_if_empty = "--only-if-empty" in sys.argv
    env = load_mysql_env()
    conn = pymysql.connect(
        host=env["MYSQL_HOST"],
        port=int(env["MYSQL_PORT"]),
        user=env["MYSQL_USER"],
        password=env["MYSQL_PASS"],
        database=env["MYSQL_DB"],
        charset="utf8mb4",
        autocommit=True,
    )
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute("SELECT id, username FROM `user` WHERE username = 'admin' LIMIT 1")
    admin = cur.fetchone()
    if not admin:
        sys.exit("未找到 username=admin 的用户")
    uid = admin["id"]

    cur.execute(
        """
        SELECT id, label, created_at, expires_at, revoked_at
        FROM user_api_token
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (uid,),
    )
    rows = cur.fetchall()
    cur.execute("SELECT UTC_TIMESTAMP() AS t")
    utc_now = cur.fetchone()["t"]

    valid = [
        r
        for r in rows
        if r["revoked_at"] is None and (r["expires_at"] is None or r["expires_at"] > utc_now)
    ]

    print("admin user_id:", uid)
    print("已有令牌记录数:", len(rows), "当前有效:", len(valid))
    for r in rows[:8]:
        print(
            f"  id={r['id']} label={r['label']!r} revoked={r['revoked_at']} expires={r['expires_at']}"
        )

    if valid and only_if_empty:
        print("\n已有有效令牌，未创建新令牌（明文无法从哈希还原）。可加参数强制刷新：python scripts/admin_openclaw_token.py --rotate")
        conn.close()
        return

    if valid and not only_if_empty and "--rotate" not in sys.argv:
        print(
            "\n已有有效令牌：数据库只存哈希，无法显示明文。\n"
            "若要生成新令牌并拿到 oc_ 明文，请执行：\n"
            "  python scripts/admin_openclaw_token.py --rotate\n"
            "将撤销当前所有有效令牌并插入一条新令牌。"
        )
        conn.close()
        return

    if valid:
        for r in valid:
            cur.execute(
                "UPDATE user_api_token SET revoked_at = UTC_TIMESTAMP() WHERE id = %s",
                (r["id"],),
            )
        print("\n已撤销原有效令牌 id:", [r["id"] for r in valid])

    raw = "oc_" + secrets.token_urlsafe(32)
    th = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    cur.execute(
        """
        INSERT INTO user_api_token (user_id, token_hash, label, expires_at, revoked_at)
        VALUES (%s, %s, %s, NULL, NULL)
        """,
        (uid, th, "openclaw-admin"),
    )
    print("\n=== 请立即复制保存（仅显示一次）===")
    print(raw)
    print("=== 填入 OpenClaw 环境变量 SYDIXON_ORDER_API_KEY，或 Authorization: Bearer ===")
    conn.close()


if __name__ == "__main__":
    main()
