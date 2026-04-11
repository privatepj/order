# Skill：从工艺/BOM 表格快速录入主数据、BOM、工序与机台（种子 SQL）

面向 **人类与 AI**：把 Excel/截图类「成品—半成品—原材料 + 工序列」整理成库内数据时，按本页顺序执行，可稳定对齐现有表结构，并产出可重复执行的 `scripts/sql/run_NN_*.sql` 增量脚本。

## 适用场景

- 有层级缩进或父子关系的 **BOM**（成品 → 多层半成品 → 原材料/采购件）。
- 「工序」列标注 **冲压 / 电镀 / 注塑 / 原材料 / 采购** 等，需要为机加工序配置 **机种 + 机台 + 操作员白名单**，供预计划测算里 `budget_machine_id` / `budget_operator_employee_id` 推荐。
- 顶层父项挂在 **`product`（成品）** 或 **`semi_material`（半成品根）** 上（`bom_header.parent_kind` 分别为 `finished` / `semi`）。

## 硬约束（与本仓库一致）

1. **禁止 DB 外键**：INSERT 只靠列语义；不写 `FOREIGN KEY`。
2. **增量脚本只增不改**：新数据必须落在**新的** `scripts/sql/run_NN_description.sql`；已存在的 `run_*.sql` 不得改写。
3. **不写死自增 id**：用 `code` / `product_code` / `name` 等唯一键 + 子查询 `(SELECT id FROM ... WHERE ... LIMIT 1)` 解析 `*_id`。
4. **`production_process_template_step`**：若库已执行 [run_63](../../scripts/sql/run_63_hr_work_type_refactor.sql)，列上可能有 `hr_work_type_id`；新库全量建表以 `00_full_schema.sql` 为准时，INSERT 可省略该列（默认 0）或显式写 0。

---

## 第一步：读表，建立「物类」清单

从表格列（常见：**物料编码**、**产品名称**、**规格**、**单个用量**、**单位**、**工序**）抽取每一行。**以表头文字为准**，不要假设「第几列字母」（不同模板列位会变）。

### `semi_material` 字段与表格列对应（易错点）

| 库字段 | 应对表格列（表头名） | 正确做法 | 错误做法 |
|--------|----------------------|----------|----------|
| `code` | 物料编码（或企业物料号列） | 与编码体系一致的唯一 `code` | — |
| `name` | **产品名称** | **逐字抄写**表中「产品名称」格，不擅自加「（电镀）」「素材」等后缀（除非表内原文就有） | 把规格、工序写进 `name` |
| `spec` | **规格** | **逐字抄写**表中「规格」格（镀层、盐雾、合金牌号、截面尺寸、胶种等） | 用「冲压件 / 注塑件 / 电镀件」等**工序名**充当规格；或与「产品名称」混写 |
| `base_unit` | 单位 | `PCS`、`KG` 等与表一致 | — |

工序含义只用于：**判断 kind**、**选择 `production_process_template`（冲压/电镀/注塑）**、**写模板步骤 `step_name`**；**不得**写进 `spec`，也**不要**用工序名改写 `name`。

| 工序列取值（示例） | 映射 `semi_material.kind` | 是否建 `production_product_routing` |
|-------------------|---------------------------|--------------------------------------|
| 原材料 | `material` | 否 |
| 采购 | `material`（或业务上仍用物料主数据） | 否 |
| 冲压 / 电镀 / 注塑 | `semi`（该行是该工序的**产出编码**） | **是**（一步一模板或共享模板） |

规则：

- **同一编码只对应一行主数据**：`semi_material.code` 全局唯一。
- 若「塑胶」等在不同父项下用量单位不同（如一行 PCS、一行 KG），仍可用**同一物料编码**；用量与单位写在 **`bom_line.quantity` / `bom_line.unit`**，与 `semi_material.base_unit` 可不完全一致（以 BOM 行为准）。

---

## 第二步：定 BOM 父子边（一层一头）

- 每一个 **父项**（成品 `product` 或半成品 `semi_material`）对应 **一条** `bom_header`：`parent_kind` + `parent_product_id` 或 `parent_material_id` + `version_no`（通常从 `1` 开始）。
- 每一个 **子项** 对应 **一条** `bom_line`：`child_kind`（`semi` / `material`）+ `child_material_id` + `line_no`（从 1 递增）+ **`quantity` = 表格「单个用量」列（按表头，不写死列字母）** + `unit`。
- 先梳理树，再写 SQL；插入顺序不必严格「子先于父」，但脚本里用 `WHERE NOT EXISTS` 防重复时，**父、子主数据应先存在**。

成品根示例：

- `bom_header`：`parent_kind='finished'`，`parent_product_id = product.id`，`parent_material_id=0`。
- `bom_line`：子件指向组装所需的 `semi_material.id` 或 `material` 行。

半成品父示例：

- `bom_header`：`parent_kind='semi'`，`parent_material_id = 父半成品.id`，`parent_product_id=0`。

---

## 第三步：机加工序 → 机种 → 机台 → 白名单操作员

测算逻辑（见 `app/services/production_cost_svc.py`）要点：

- 工序模板步的 **`resource_kind` 应为 `machine_type`**，并填 **`machine_type_id`**，才会走「机台 + `machine_operator_allowlist`」推荐。
- 每一类机加工序（如冲压、电镀、注塑）建议至少：
  - 一条 **`machine_type`**（唯一 `code`）；
  - 一条 **`machine`**（`machine_no` 唯一，`status='enabled'`）；
  - 一条 **`hr_employee`**（`company_id` 与种子库一致，如 `1`）；
  - 一条 **`machine_operator_allowlist`**（`machine_id` + `employee_id`，`is_active=1`）。

可为多产品线加前缀机种编码（如 `B7_STAMP`），避免与现网机种 `code` 冲突。

---

## 第四步：工序模板与产品路由

- **`production_process_template`**：头 + **`production_process_template_step`**（至少 `step_no`、`step_name`、`resource_kind`、`machine_type_id`、工时占位）。
- **推荐建模**（与多层 BOM + 测算展开一致）：**每个「厂内加工产出」的半成品** 绑定 **一条** `production_product_routing`：
  - `target_kind='semi'`，`target_id=semi_material.id`；
  - `template_id` 指向「冲压-only / 电镀-only / 注塑-only」三类模板之一（可三个模板被多个半成品共用）；
  - `created_by` 使用已有管理员 `user.id`（如种子库 `1`）；
  - `product_id` 在半成品路由上填 `0`。

成品仅有 BOM、无厂内总装工序时，**可不建** `target_kind='finished'` 的路由（无步骤则测算不会在成品上生成工序）。

---

## 第五步：写成可重复执行的种子 SQL

推荐模式（与 [run_73](../../scripts/sql/run_73_b7_typec9p_bom_process_seed.sql) 一致）：

1. 脚本头：`USE sydixon_order;`（或部署约定库名）+ `SET NAMES utf8mb4;`。
2. **`semi_material`**：`INSERT ... SELECT ... FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM semi_material WHERE code=?)`。
3. **`machine_type` / `machine` / `hr_employee` / `machine_operator_allowlist`**：对唯一业务键（`code`、`machine_no`、`employee_no`）做 `NOT EXISTS`。
4. **模板与步骤**：模板按唯一 `name` 防重；步骤按 `(template_id, step_no)` 防重。
5. **`product`**：按 `product_code` 防重。
6. **`bom_header`**：按 `(parent_kind, parent_product_id, parent_material_id, version_no)` 防重。
7. **`bom_line`**：按 `(bom_header_id, line_no)` 防重。
8. **`production_product_routing`**：按 `(target_kind, target_id)` 防重；`template_id` 用子查询 `(SELECT id ... ORDER BY id LIMIT 1)` 避免 JOIN 放大。

**小数位数**：`bom_line.quantity` 为 `decimal(18,4)`；若表上「单个用量」超过 4 位小数，在脚本注释中说明取舍规则。

**同一物料编码、表中多行「规格」不同**（如塑胶两行）：在 `semi_material.spec` 中可合并为一条（用分号等），或在 `remark` 说明业务分支；`name` 仍以表内「产品名称」为准。

---

## 第六步：部署后自检 SQL（可选）

```sql
-- 物料条数（按你的编码前缀调整）
SELECT kind, COUNT(*) FROM semi_material WHERE remark LIKE '%B7 seed%' OR code LIKE 'F.%' GROUP BY kind;

-- 成品 BOM 行数
SELECT h.id, COUNT(l.id) FROM bom_header h
JOIN product p ON p.id = h.parent_product_id AND p.product_code = '你的成品编码'
JOIN bom_line l ON l.bom_header_id = h.id
WHERE h.parent_kind = 'finished' AND h.version_no = 1 GROUP BY h.id;

-- 半成品路由是否齐套
SELECT sm.code, r.id IS NOT NULL AS has_routing
FROM semi_material sm
LEFT JOIN production_product_routing r ON r.target_kind='semi' AND r.target_id = sm.id AND r.is_active=1
WHERE sm.kind='semi' AND sm.remark LIKE '%你的种子标记%';
```

---

## 相关代码与文档

| 主题 | 路径 |
|------|------|
| BOM 模型 | `app/models/bom.py` |
| 半成品主数据 | `app/models/semi_material.py` |
| 工序解析与测算消费 | `app/services/production_svc.py`（`_resolve_process_steps_for_target`） |
| 机台+人推荐 | `app/services/production_cost_svc.py` |
| 域说明（骨架） | [../../02_domains/bom.md](../../02_domains/bom.md)、[../../02_domains/production.md](../../02_domains/production.md) |
| B7 示例种子（name/规格对齐主数据表） | [../../scripts/sql/run_73_b7_typec9p_bom_process_seed.sql](../../scripts/sql/run_73_b7_typec9p_bom_process_seed.sql) |
| B7 规格早期纠错（曾误写工序名为 spec） | [../../scripts/sql/run_74_b7_semi_material_spec_from_column_g.sql](../../scripts/sql/run_74_b7_semi_material_spec_from_column_g.sql) |
| B7 name/spec 与「产品名称」「规格」表完全一致 | [../../scripts/sql/run_75_b7_semi_material_name_spec_master_table.sql](../../scripts/sql/run_75_b7_semi_material_name_spec_master_table.sql) |

---

## AI 执行清单（简版）

1. 解析表格：物料编码、**产品名称**、**规格**、单位、**单个用量**、工序列；`name`/`spec` 与表内「产品名称」「规格」**逐字一致**，禁止用工序名填 `spec`、禁止在 `name` 上自造后缀。  
2. 分类写入 `semi_material`（`material` / `semi`）。  
3. 为冲压/电镀/注塑各建 `machine_type` + `machine` + `hr_employee` + `machine_operator_allowlist`。  
4. 建三类 `production_process_template` + `production_process_template_step`（`machine_type` 资源）。  
5. 对每个加工产出半成品插入 `production_product_routing`。  
6. 建 `product`（若需要成品根）+ 全树 `bom_header` / `bom_line`。  
7. 新增 `run_NN_*.sql`，全部防重；不写死 id。
