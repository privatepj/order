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
| `README.md` | 本说明 |

---

## 与历史脚本的关系

- **新库**只维护 **`00_full_schema.sql`**，不再保留根目录下的重复全量脚本。
- 历史上分散在 `scripts/` 下的增量 `migrate_*.sql` / `alter_*.sql` / `add_*.sql` 已全部并入 **`01_migrations_for_old_db.sql`**（含 **`audit_log`** 表）；旧库升级执行该文件即可。

部署完成后，请参照项目根目录 **《项目整体部署.md》** 配置 `.env`、启动应用（如 gunicorn）等。
