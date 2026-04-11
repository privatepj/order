from app import db


class OrchestratorEvent(db.Model):
    __tablename__ = "orchestrator_event"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    biz_key = db.Column(db.String(128), nullable=False, index=True)
    trace_id = db.Column(db.String(64), nullable=True, index=True)
    idempotency_key = db.Column(db.String(128), nullable=False, unique=True)
    payload = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="new", index=True)
    error_message = db.Column(db.String(500), nullable=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    occurred_at = db.Column(db.DateTime, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)


class OrchestratorAction(db.Model):
    __tablename__ = "orchestrator_action"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_id = db.Column(db.BigInteger, nullable=False, index=True)
    action_type = db.Column(db.String(64), nullable=False, index=True)
    action_key = db.Column(db.String(128), nullable=False, unique=True)
    payload = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    next_retry_at = db.Column(db.DateTime, nullable=True, index=True)
    error_message = db.Column(db.String(500), nullable=True)
    executed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)


class OrchestratorAuditLog(db.Model):
    __tablename__ = "orchestrator_audit_log"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_id = db.Column(db.BigInteger, nullable=True, index=True)
    action_id = db.Column(db.BigInteger, nullable=True, index=True)
    level = db.Column(db.String(16), nullable=False, default="info")
    message = db.Column(db.String(500), nullable=False)
    detail = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)


class OrchestratorAiAdvice(db.Model):
    __tablename__ = "orchestrator_ai_advice"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_id = db.Column(db.BigInteger, nullable=False, index=True)
    advice_type = db.Column(db.String(64), nullable=False)
    recommended_action = db.Column(db.String(128), nullable=False)
    confidence = db.Column(db.Numeric(26, 8), nullable=True)
    reason = db.Column(db.String(1000), nullable=True)
    meta = db.Column(db.JSON, nullable=True)
    is_adopted = db.Column(db.Boolean, nullable=False, default=False, index=True)
    adopted_by = db.Column(db.Integer, nullable=True)
    adopted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)


class OrchestratorAiAdviceMetric(db.Model):
    __tablename__ = "orchestrator_ai_advice_metric"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    advice_id = db.Column(db.BigInteger, nullable=False, index=True)
    event_id = db.Column(db.BigInteger, nullable=False, index=True)
    advice_type = db.Column(db.String(64), nullable=False, index=True)
    is_adopted = db.Column(db.Boolean, nullable=False, default=False, index=True)
    adopted_latency_seconds = db.Column(db.Integer, nullable=True)
    result_score = db.Column(db.Numeric(26, 8), nullable=True)
    metric_note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)


class OrchestratorRuleProfile(db.Model):
    __tablename__ = "orchestrator_rule_profile"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    rule_code = db.Column(db.String(64), nullable=False, unique=True, index=True)
    rule_name = db.Column(db.String(128), nullable=False)
    allow_alternative = db.Column(db.Boolean, nullable=False, default=False)
    allow_outsource = db.Column(db.Boolean, nullable=False, default=False)
    allow_secondary_supplier = db.Column(db.Boolean, nullable=False, default=False)
    priority = db.Column(db.Integer, nullable=False, default=100, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    remark = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)


class OrchestratorReplayJob(db.Model):
    __tablename__ = "orchestrator_replay_job"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    event_id = db.Column(db.BigInteger, nullable=False, index=True)
    dry_run = db.Column(db.Boolean, nullable=False, default=False)
    allow_high_risk = db.Column(db.Boolean, nullable=False, default=False)
    selected_actions = db.Column(db.JSON, nullable=True)
    blocked_actions = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="done")
    created_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
