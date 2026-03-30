# SQL 脚本说明（服务器部署用）

本目录为**整合后的 SQL**，便于在服务器上一键或按序执行。

## 部署方式

### 新服务器（全新部署）

**只需执行一个文件：**

```bash
# 1. 创建数据库（若尚未创建）
mysql -u 用户名 -p -e "CREATE DATABASE IF NOT EXISTS sydixon_order DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 执行全量建表
mysql -u 用户名 -p sydixon_order < scripts/sql/00_full_schema.sql
```

或在 MySQL 客户端内：

```sql
CREATE DATABASE IF NOT EXISTS sydixon_order DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sydixon_order;
SOURCE /path/to/scripts/sql/00_full_schema.sql;
```

执行后将得到：全部表结构 + 初始角色 + 管理员账号（admin / password，请首次登录后修改）。

**不要**对新库执行 `01_migrations_for_old_db.sql`。

---

### 从旧版本库升级

若数据库是早期版本（缺少经营主体、快递、客户简称、订单样品、付款类型、`role.allowed_menu_keys` 等），可执行增量迁移：

```bash
# 执行前请先备份数据库
mysql -u 用户名 -p sydixon_order < scripts/sql/01_migrations_for_old_db.sql
```

若某条语句报错「Duplicate column name」等（表示该列已存在），可忽略该条并继续执行后续语句。

---

## 文件一览

| 文件 | 用途 |
|------|------|
| `00_full_schema.sql` | 全量建表 + 初始数据，**新库部署只执行此文件**（无数据库级外键） |
| `00_reset_drop_all_tables.sql` | 仅删除全部业务表；删后需再执行 `00_full_schema.sql`（开发重建用，先备份） |
| `01_migrations_for_old_db.sql` | 增量迁移，仅用于从旧库升级（含每日库存表 `inventory_daily_*`） |
| `run_16_seed_nav_capability.sql` 及 `run_*.sql` | 旧库按需补跑；**勿向已使用过的 `run_XX` 再追加 INSERT**，新增能力只新建更高编号的 `run_XX_*.sql`（幂等），否则已跑过早期脚本的库会漏数据 |
| `run_30_add_production_tables.sql` / `run_31_production_rbac.sql` | 生产管理：新增生产预计划/工作单/缺料明细 + 导航/能力键 |
| `run_23_openclaw_user_token_and_caps.sql` | OpenClaw：`user_api_token` 表 + `openclaw.*` 能力键（旧库升级用；新库已并入 `00_full_schema.sql`） |
| `run_24_openclaw_confirm_flow_caps.sql` | OpenClaw 确认制：主体/产品查询、建客户与客户产品、订单/送货预览等能力键 |
| `user_today/` | 用户脚本目录：存放“今天新增/改动”的 SQL（由 `scripts/run_user_sql_batch.py` 执行，按 sha256 跳过重复脚本） |
| `README.md` | 本说明 |

---

## 与历史脚本的关系

- **新库**只维护 **`00_full_schema.sql`**，不再保留根目录下的重复全量脚本。
- 历史上分散在 `scripts/` 下的增量 `migrate_*.sql` / `alter_*.sql` / `add_*.sql` 已全部并入 **`01_migrations_for_old_db.sql`**（含 **`audit_log`** 表）；旧库升级执行该文件即可。

部署完成后，请参照项目根目录 **《项目整体部署.md》** 配置 `.env`、启动应用（如 gunicorn）等。

---
## 用户脚本目录（user_today）
把今天新增/改动的 SQL 放入 `scripts/sql/user_today/`，然后执行：

```bash
python scripts/run_user_sql_batch.py
```

执行器会根据每个文件的 sha256 在数据库表 `sql_user_script_run_log` 中记录已执行脚本；命中则跳过，从而避免增量部署时重复执行同一批脚本。

注意：执行器会粗分割 SQL（按 `;`），并自动忽略 `USE ...;` 行。建议用户脚本尽量保持成“补丁式多条语句”，不要依赖复杂存储过程/函数定义中的分号行为。
