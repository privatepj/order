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
- `SYDIXON_ORDER_API_KEY`：与订单系统 `.env` 中 `OPENCLAW_API_KEY` 一致。

订单系统需已配置 `OPENCLAW_API_KEY` 并启动；默认快递「顺丰」需在系统中存在且已录入运单号池。
