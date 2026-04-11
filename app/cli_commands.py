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
from app.models import (
    HrDepartment,
    HrDepartmentPieceRate,
    HrEmployee,
    HrEmployeeCapability,
    HrEmployeeScheduleBooking,
    HrWorkType,
    HrWorkTypePieceRate,
    Machine,
    MachineOperatorAllowlist,
    MachineType,
    OrchestratorAiAdvice,
    ProductionProcessNode,
    ProductionProcessTemplateStep,
    ProductionProductRoutingStep,
    ProductionRoutingNodeOverride,
    ProductionWorkOrderOperation,
    ProductionWorkOrderOperationPlan,
    User,
    UserApiToken,
)
from app.services import orchestrator_engine
from app.services.hr_employee_capability_svc import update_employee_capability
from app.services.hr_work_type_svc import ensure_work_type, sync_employee_work_types


def register_cli(app):
    app.cli.add_command(openclaw_token_create)
    app.cli.add_command(openclaw_token_revoke)
    app.cli.add_command(orchestrator_scan_overdue)
    app.cli.add_command(orchestrator_ai_metric_backfill)
    app.cli.add_command(orchestrator_health_check)
    app.cli.add_command(hr_employee_capability_sync)
    app.cli.add_command(hr_work_type_backfill)


def _clean_name(raw) -> str:
    return (raw or "").strip()


def _filtered_company_ids(company_ids):
    out = {int(x) for x in company_ids if int(x) > 0}
    return out


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


@click.command("hr-work-type-backfill")
@click.option("--company-id", "company_ids", type=int, multiple=True, help="仅处理指定 company_id，可重复传入。")
@click.option("--dry-run", is_flag=True, help="只预演不提交。")
@with_appcontext
def hr_work_type_backfill(company_ids, dry_run: bool):
    """按旧部门 / job_title / 能力 / 排产日志回填工种主数据与关联。"""

    scoped_company_ids = _filtered_company_ids(company_ids)

    def in_scope(company_id: int) -> bool:
        return not scoped_company_ids or int(company_id or 0) in scoped_company_ids

    stats = {
        "work_types_created": 0,
        "employees_updated": 0,
        "capability_rows_updated": 0,
        "booking_rows_updated": 0,
        "piece_rates_upserted": 0,
        "machine_rows_updated": 0,
        "production_rows_updated": 0,
    }
    unresolved: list[str] = []

    departments = HrDepartment.query.order_by(HrDepartment.company_id.asc(), HrDepartment.id.asc()).all()
    dept_to_work_type_id: dict[int, int] = {}

    for department in departments:
        company_id = int(department.company_id or 0)
        if not in_scope(company_id):
            continue
        name = _clean_name(department.name)
        if not name:
            unresolved.append(f"department:{department.id}: empty name")
            continue
        existed = HrWorkType.query.filter_by(company_id=company_id, name=name).first()
        work_type = existed or ensure_work_type(company_id=company_id, name=name)
        if existed is None and work_type is not None:
            stats["work_types_created"] += 1
        if work_type:
            dept_to_work_type_id[int(department.id)] = int(work_type.id)

    employees = HrEmployee.query.order_by(HrEmployee.company_id.asc(), HrEmployee.id.asc()).all()
    extra_work_type_ids_by_employee: dict[int, set[int]] = {}

    for employee in employees:
        company_id = int(employee.company_id or 0)
        if not in_scope(company_id):
            continue
        title_name = _clean_name(employee.job_title)
        if title_name:
            existed = HrWorkType.query.filter_by(company_id=company_id, name=title_name).first()
            work_type = existed or ensure_work_type(company_id=company_id, name=title_name)
            if existed is None and work_type is not None:
                stats["work_types_created"] += 1

    capability_rows = HrEmployeeCapability.query.order_by(HrEmployeeCapability.id.asc()).all()
    for row in capability_rows:
        employee = db.session.get(HrEmployee, int(row.employee_id or 0))
        if not employee or not in_scope(int(employee.company_id or 0)):
            continue
        work_type_id = int(row.work_type_id or 0)
        if work_type_id <= 0:
            work_type_id = int(dept_to_work_type_id.get(int(row.hr_department_id or 0), 0))
            if work_type_id > 0:
                row.work_type_id = work_type_id
                stats["capability_rows_updated"] += 1
            else:
                unresolved.append(
                    f"capability:{row.id}: employee={row.employee_id}, hr_department_id={row.hr_department_id}"
                )
                continue
        extra_work_type_ids_by_employee.setdefault(int(row.employee_id), set()).add(work_type_id)

    booking_rows = HrEmployeeScheduleBooking.query.order_by(HrEmployeeScheduleBooking.id.asc()).all()
    for row in booking_rows:
        employee = db.session.get(HrEmployee, int(row.employee_id or 0))
        if not employee or not in_scope(int(employee.company_id or 0)):
            continue
        work_type_id = int(row.work_type_id or 0)
        if work_type_id <= 0 and int(row.hr_department_id or 0) > 0:
            work_type_id = int(dept_to_work_type_id.get(int(row.hr_department_id or 0), 0))
            if work_type_id > 0:
                row.work_type_id = work_type_id
                stats["booking_rows_updated"] += 1
            else:
                unresolved.append(
                    f"booking:{row.id}: employee={row.employee_id}, hr_department_id={row.hr_department_id}"
                )
                continue
        if work_type_id > 0:
            extra_work_type_ids_by_employee.setdefault(int(row.employee_id), set()).add(work_type_id)

    for employee in employees:
        company_id = int(employee.company_id or 0)
        if not in_scope(company_id):
            continue

        current_main_id = int(employee.main_work_type_id or 0)
        main_work_type_id = current_main_id if current_main_id > 0 else 0

        if main_work_type_id <= 0:
            title_name = _clean_name(employee.job_title)
            if title_name:
                row = HrWorkType.query.filter_by(company_id=company_id, name=title_name).first()
                if row:
                    main_work_type_id = int(row.id)
        if main_work_type_id <= 0 and int(employee.department_id or 0) > 0:
            main_work_type_id = int(dept_to_work_type_id.get(int(employee.department_id), 0))

        secondary_ids = sorted(extra_work_type_ids_by_employee.get(int(employee.id), set()))
        before_main = int(employee.main_work_type_id or 0)
        before_all = {
            int(link.work_type_id)
            for link in (employee.work_type_links or [])
            if int(link.work_type_id or 0) > 0
        }
        sync_employee_work_types(
            employee=employee,
            main_work_type_id=(main_work_type_id or None),
            secondary_work_type_ids=secondary_ids,
        )
        after_all = {
            int(link.work_type_id)
            for link in (employee.work_type_links or [])
            if int(link.work_type_id or 0) > 0
        }
        if before_main != int(employee.main_work_type_id or 0) or before_all != after_all:
            stats["employees_updated"] += 1

    piece_rates = HrDepartmentPieceRate.query.order_by(HrDepartmentPieceRate.id.asc()).all()
    for row in piece_rates:
        if not in_scope(int(row.company_id or 0)):
            continue
        work_type_id = int(dept_to_work_type_id.get(int(row.hr_department_id or 0), 0))
        if work_type_id <= 0:
            unresolved.append(f"piece_rate:{row.id}: hr_department_id={row.hr_department_id}")
            continue
        target = HrWorkTypePieceRate.query.filter_by(
            company_id=int(row.company_id),
            work_type_id=work_type_id,
            period=row.period,
        ).first()
        if target is None:
            target = HrWorkTypePieceRate(
                company_id=int(row.company_id),
                work_type_id=work_type_id,
                period=row.period,
                created_by=int(row.created_by or 0),
            )
            db.session.add(target)
        target.rate_per_unit = row.rate_per_unit
        target.remark = row.remark
        stats["piece_rates_upserted"] += 1

    def _backfill_attr(rows, legacy_attr: str, new_attr: str, stat_key: str):
        for row in rows:
            legacy_id = int(getattr(row, legacy_attr, 0) or 0)
            new_id = int(getattr(row, new_attr, 0) or 0)
            if new_id > 0 or legacy_id <= 0:
                continue
            mapped_id = int(dept_to_work_type_id.get(legacy_id, 0))
            if mapped_id <= 0:
                unresolved.append(f"{row.__class__.__name__}:{getattr(row, 'id', 0)}: legacy={legacy_id}")
                continue
            setattr(row, new_attr, mapped_id)
            stats[stat_key] += 1

    _backfill_attr(MachineType.query.order_by(MachineType.id.asc()).all(), "default_capability_hr_department_id", "default_capability_work_type_id", "machine_rows_updated")
    _backfill_attr(Machine.query.order_by(Machine.id.asc()).all(), "default_capability_hr_department_id", "default_capability_work_type_id", "machine_rows_updated")
    _backfill_attr(MachineOperatorAllowlist.query.order_by(MachineOperatorAllowlist.id.asc()).all(), "capability_hr_department_id", "capability_work_type_id", "machine_rows_updated")
    _backfill_attr(ProductionProcessTemplateStep.query.order_by(ProductionProcessTemplateStep.id.asc()).all(), "hr_department_id", "hr_work_type_id", "production_rows_updated")
    _backfill_attr(ProductionProductRoutingStep.query.order_by(ProductionProductRoutingStep.id.asc()).all(), "hr_department_id_override", "hr_work_type_id_override", "production_rows_updated")
    _backfill_attr(ProductionProcessNode.query.order_by(ProductionProcessNode.id.asc()).all(), "hr_department_id", "hr_work_type_id", "production_rows_updated")
    _backfill_attr(ProductionRoutingNodeOverride.query.order_by(ProductionRoutingNodeOverride.id.asc()).all(), "hr_department_id_override", "hr_work_type_id_override", "production_rows_updated")
    _backfill_attr(ProductionWorkOrderOperation.query.order_by(ProductionWorkOrderOperation.id.asc()).all(), "hr_department_id", "hr_work_type_id", "production_rows_updated")
    _backfill_attr(ProductionWorkOrderOperationPlan.query.order_by(ProductionWorkOrderOperationPlan.id.asc()).all(), "hr_department_id", "hr_work_type_id", "production_rows_updated")

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    click.echo(
        "work_type_backfill done dry_run={dry_run} work_types_created={work_types_created} "
        "employees_updated={employees_updated} capability_rows_updated={capability_rows_updated} "
        "booking_rows_updated={booking_rows_updated} piece_rates_upserted={piece_rates_upserted} "
        "machine_rows_updated={machine_rows_updated} production_rows_updated={production_rows_updated}".format(
            dry_run=int(bool(dry_run)),
            **stats,
        )
    )
    if unresolved:
        click.echo("unresolved_items:")
        for item in unresolved[:200]:
            click.echo(f"- {item}")
        if len(unresolved) > 200:
            click.echo(f"- ... and {len(unresolved) - 200} more")


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    sys.exit(app.cli.main(args=sys.argv[1:]))
