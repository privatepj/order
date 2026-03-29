import hashlib
import secrets
from datetime import datetime, timedelta

import click
from flask.cli import with_appcontext

from app import db
from app.models import User, UserApiToken


def register_cli(app):
    app.cli.add_command(openclaw_token_create)
    app.cli.add_command(openclaw_token_revoke)


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
