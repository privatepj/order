# 本地开发

详细命令与虚拟环境路径以仓库规范为准：

- **[AGENTS.md](../../AGENTS.md)** — 推荐命令（`.\.venv\Scripts\python.exe`、pytest、ruff）
- **[CLAUDE.md](../../CLAUDE.md)** — AI 助手常用命令与架构要点
- **[README.md](../../README.md)** — 功能概览、`.env`、启动方式

## 摘要

```bash
# 安装依赖后启动
python run.py

# 测试
python -m pytest

# 静态检查
python -m ruff check app
python -m ruff format app
```

## 默认账号

开发库初始化后通常为 `admin` / `password`（首次登录后请修改）。

## 文档同步提醒

若修改业务逻辑、权限、表结构或 OpenClaw 契约，请同步更新：

- `docs/02_domains/` 对应域文档
- `docs/04_ai/project-skill/` 中相关速查或映射
- 可选：`docs/changes/` 记一条变更说明

详见 [changes/README.md](../changes/README.md)。
