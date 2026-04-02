import hashlib
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

# `python app\cli_commands.py ...` puts `app/` on sys.path; project root must be on path for `import app`.
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import click
from flask.cli import with_appcontext

from app import db
from app.models import User, UserApiToken
from app.models import OrchestratorAiAdvice
from app.services import orchestrator_engine
from app.services.hr_employee_capability_svc import update_employee_capability


def register_cli(app):
    app.cli.add_command(openclaw_token_create)
    app.cli.add_command(openclaw_token_revoke)
    app.cli.add_command(orchestrator_scan_overdue)
    app.cli.add_command(orchestrator_ai_metric_backfill)
    app.cli.add_command(orchestrator_health_check)
    app.cli.add_command(hr_employee_capability_sync)


@click.command("openclaw-token-create")
@click.argument("username")
@click.option("--label", default="", help="令牌备注（可选）")
@click.option("--days", default=None, type=int, help="有效天数；默认不过期")
@with_appcontext
def openclaw_token_create(username, label, days):
    """为指定登录名创建 OpenClaw API 令牌（明文仅打印一次，请妥善保存）。"""
    user = User.query.filter_by(username=username.strip()).first()
    if not user:
        raise click.ClickException(f"用户不存在: {username}")
    if not user.is_active:
        raise click.ClickException("用户已停用")
    if getattr(user, "role_code", None) == "pending":
        raise click.ClickException("用户尚未分配角色，无法发令牌")

    raw = "oc_" + secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    expires_at = None
    if days is not None and days > 0:
        expires_at = datetime.utcnow() + timedelta(days=days)

    row = UserApiToken(
        user_id=user.id,
        token_hash=token_hash,
        label=(label.strip() or None),
        expires_at=expires_at,
    )
    db.session.add(row)
    db.session.commit()
    click.echo("以下令牌仅显示一次，请复制到 OpenClaw 环境变量 SYDIXON_ORDER_API_KEY：")
    click.echo(raw)


@click.command("openclaw-token-revoke")
@click.argument("token_id", type=int)
@with_appcontext
def openclaw_token_revoke(token_id):
    """按 user_api_token.id 撤销令牌。"""
    row = db.session.get(UserApiToken, token_id)
    if not row:
        raise click.ClickException("令牌不存在")
    row.revoked_at = datetime.utcnow()
    db.session.add(row)
    db.session.commit()
    click.echo(f"已撤销 token id={token_id}")


@click.command("orchestrator-scan-overdue")
@click.option("--created-by", default=1, type=int, help="执行人 user_id，默认 1")
@with_appcontext
def orchestrator_scan_overdue(created_by):
    """触发一次订单超时扫描并执行调度动作。"""
    evt = orchestrator_engine.emit_overdue_scan_event(
        source="cli.orchestrator_scan_overdue",
        source_id=int(created_by),
        version=int(datetime.utcnow().timestamp()),
    )
    out = orchestrator_engine.process_event(int(evt.id), created_by=int(created_by))
    db.session.commit()
    click.echo(f"scan event_id={evt.id}, status={out.get('status')}, actions={len(out.get('actions') or [])}")


@click.command("orchestrator-ai-metric-backfill")
@with_appcontext
def orchestrator_ai_metric_backfill():
    """补写历史 AI 建议指标。"""
    rows = OrchestratorAiAdvice.query.order_by(OrchestratorAiAdvice.id.asc()).all()
    created = 0
    for row in rows:
        metric = orchestrator_engine.update_or_create_ai_metric_from_advice(int(row.id))
        if metric:
            created += 1
    db.session.commit()
    click.echo(f"ai metric backfill done, processed={len(rows)}, upserted={created}")


@click.command("orchestrator-health-check")
@with_appcontext
def orchestrator_health_check():
    """打印 orchestrator 健康状态摘要。"""
    out = orchestrator_engine.get_health_summary()
    click.echo(f"healthy={out.get('healthy')}")
    click.echo(
        "dead_actions={dead_actions}, failed_events_24h={failed_events_24h}, success_rate_24h={success_rate_24h}".format(
            dead_actions=out.get("dead_actions"),
            failed_events_24h=out.get("failed_events_24h"),
            success_rate_24h=out.get("success_rate_24h"),
        )
    )


@click.command("hr-employee-capability-sync")
@click.option(
    "--to",
    "to_raw",
    default="",
    help="统计截至时间（ISO 格式，例如 2026-04-02T10:00:00；默认现在，对齐到分钟）。",
)
@click.option(
    "--max-backfill-minutes",
    default=10080,
    type=int,
    show_default=True,
    help="单次最多回溯的分钟窗口数（默认 7 天）；更早的数据需调大或分批执行。",
)
@with_appcontext
def hr_employee_capability_sync(to_raw: str, max_backfill_minutes: int):
    """按分钟粒度增量同步人员能力表（单次调用会从最早排班起顺序处理到 --to，非定时任务本身）。"""
    to_dt = datetime.fromisoformat(to_raw) if to_raw else datetime.now()
    out = update_employee_capability(to_dt=to_dt, max_backfill_minutes=max_backfill_minutes)
    db.session.commit()
    click.echo(
        "capability sync done, groups_updated={groups_updated}, cap_rows_created={cap_rows_created}".format(
            groups_updated=out.get("groups_updated"), cap_rows_created=out.get("cap_rows_created")
        )
    )


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    sys.exit(app.cli.main(args=sys.argv[1:]))
