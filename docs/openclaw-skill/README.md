# OpenClaw 技能：sydixon-order

将本目录复制到 OpenClaw 技能目录下即可使用：

```bash
# 创建技能目录
mkdir -p ~/.openclaw/skills/sydixon-order
# 复制 SKILL.md（从项目根目录执行）
cp docs/openclaw-skill/SKILL.md ~/.openclaw/skills/sydixon-order/
```

配置环境变量（在 OpenClaw 运行环境中）：

- `SYDIXON_ORDER_URL`：订单系统 base URL，如 `http://127.0.0.1:5000` 或内网地址。
- `SYDIXON_ORDER_API_KEY`：全局 `OPENCLAW_API_KEY`，或订单系统侧 `flask openclaw-token-create <用户名>` 生成的用户令牌。

订单系统需已配置凭据并启动；数据库连接请使用 **utf8mb4**（如 `DATABASE_URL` 带 `?charset=utf8mb4`），OpenClaw 请求 JSON 使用 **UTF-8**（建议 `Content-Type: application/json; charset=utf-8`），否则中文易乱码。旧库升级 OpenClaw：执行 `run_23_openclaw_user_token_and_caps.sql` 与 `run_24_openclaw_confirm_flow_caps.sql`。用户令牌须在角色中勾选所需 `openclaw.*`（含 `companies`/`products`、预览、创建等）。技能遵循 **输入确认制度**：**下单并送货**时须 **双表一步确认**（同一条消息两个 Markdown 表，用户只确认一次），详见 `SKILL.md`。**仓库里改了 `SKILL.md` 后，务必重新执行上面的 `cp` 覆盖 OpenClaw 技能目录**，否则客户端仍用旧说明、会继续分两步问确认。默认快递「顺丰」需在系统中存在且已录入运单号池。
