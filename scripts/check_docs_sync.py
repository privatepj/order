#!/usr/bin/env python3
"""
提醒：若改动了核心业务代码或 SQL，是否同时改动了 docs/。

默认：仅打印 WARNING，退出码 0。
--strict：若命中触发路径且本次 diff 中没有任何 docs/ 变更，则退出码 1。

检测范围（相对仓库根）：
  - 工作区相对 HEAD 的改动：git diff --name-only HEAD
  - 暂存区相对 HEAD 的改动：git diff --cached --name-only HEAD

用法：
  python scripts/check_docs_sync.py
  python scripts/check_docs_sync.py --strict
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TRIGGER_PREFIXES = (
    "app/main/",
    "app/services/",
    "app/models/",
    "app/auth/",
    "app/openclaw/",
    "scripts/sql/",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _git_diff_names(*, cached: bool) -> str:
    """Use core.quotepath=false so non-ASCII paths (e.g. 中文文件名) stay readable on Windows."""
    cmd = ["git", "-c", "core.quotepath=false", "diff", "--name-only", "HEAD"]
    if cached:
        cmd.insert(cmd.index("diff") + 1, "--cached")
    return subprocess.check_output(cmd, cwd=_repo_root(), text=True, stderr=subprocess.DEVNULL)


def _changed_files() -> set[str]:
    out = set()
    for cached in (False, True):
        try:
            text = _git_diff_names(cached=cached)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return set()
        for line in text.splitlines():
            line = line.strip().replace("\\", "/")
            if line:
                out.add(line)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs/ touched when app or SQL changes.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if trigger paths changed but docs/ did not.",
    )
    args = parser.parse_args()

    files = _changed_files()
    if not files:
        return 0

    triggered = [f for f in files if any(f.startswith(p) for p in TRIGGER_PREFIXES)]
    doc_touched = any(f.startswith("docs/") for f in files)

    if not triggered:
        return 0

    if doc_touched:
        return 0

    msg = (
        "check_docs_sync: working tree touches app/* or scripts/sql/ but no docs/ files changed.\n"
        "Sync docs/02_domains/, docs/04_ai/project-skill/, etc. (see docs/changes/README.md).\n"
        f"Sample changed paths (max 12): {sorted(list(files))[:12]}"
    )
    print(msg, file=sys.stderr)
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
