# 数据库迁移与约定

## 权威说明

请先阅读 **[scripts/sql/README.md](../../scripts/sql/README.md)**（新库 / 旧库升级路径、文件一览）。

## 硬约束（必须遵守）

1. **禁止数据库级外键**  
   MySQL 脚本中不得新增 `FOREIGN KEY` / `REFERENCES`。SQLAlchemy 列上不使用 `ForeignKey()`；关系用 `primaryjoin` + `foreign(子表.逻辑外键列)`。  
   规则文件：`.cursor/rules/no-database-foreign-keys.mdc`

2. **增量脚本只增不改**  
   已存在的 `scripts/sql/run_*.sql` **不得**修改内容；新变更只能新增下一个 `run_NN_description.sql`。全量 `00_full_schema.sql` 可与当前 schema 对齐而修改。  
   规则文件：`.cursor/rules/incremental-sql-append-only.mdc`

## 新库 vs 旧库

| 场景 | 操作 |
|------|------|
| 全新库 | 只执行 `00_full_schema.sql` |
| 从早期结构升级 | `01_migrations_for_old_db.sql` + 按需补跑 `run_*.sql`（按发布说明顺序） |

## ORM 逻辑外键示例

```python
# 子表持有 batch_id 时，在子表侧用 foreign() 标明“外键侧”
movements = db.relationship(
    "InventoryMovement",
    back_populates="batch",
    primaryjoin="InventoryMovementBatch.id == foreign(InventoryMovement.movement_batch_id)",
)
```

更多模式见 [项目 Skill：DB 规则](../04_ai/project-skill/db_rules_and_patterns.md)。

## user_today 目录

用于当日/临时脚本批量执行与去重，见 `scripts/sql/README.md` 中 `user_today/` 说明。
