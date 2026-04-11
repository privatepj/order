# 数据库与 ORM 规则（速查）

## SQL

- **不要**在 `scripts/sql/**/*.sql` 中新增 `CONSTRAINT ... FOREIGN KEY` 或 `REFERENCES`。
- **不要**修改已发布的 `scripts/sql/run_*.sql`；新增下一个 `run_NN_description.sql`。
- 新库以 `00_full_schema.sql` 为准；与增量脚本并存时，全量文件应随时间推进保持最新结构。

## 数值精度

- 业务金额/数量/工时等列与 ORM 对齐为 **MySQL `decimal(26,8)`** / **`db.Numeric(26, 8)`**（小数标度 8）；舍入与对外 JSON 字符串见 `app/utils/decimal_scale.py`（`quantize_decimal` / `json_decimal`）。

## SQLAlchemy

- 列上**不使用** `ForeignKey()`。
- 一对多/多对一：显式 `primaryjoin`，在**持有外键列的一侧**使用 `foreign(子表.外键列)`。

示例（批次 ↔ 流水）：

```python
movements = db.relationship(
    "InventoryMovement",
    back_populates="batch",
    primaryjoin="InventoryMovementBatch.id == foreign(InventoryMovement.movement_batch_id)",
)
```

## 文档

- 深入说明：[../../01_development/db-migrations.md](../../01_development/db-migrations.md)  
- 仓库规则：`.cursor/rules/no-database-foreign-keys.mdc`、`incremental-sql-append-only.mdc`
