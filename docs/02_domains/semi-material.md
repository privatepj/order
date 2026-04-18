# 业务域：半成品 / 物料主数据

> 本文档为**骨架**。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_semi_material.py` |
| 模板 | `app/templates/semi_material/*.html` |
| 模型 | `app/models/` 中与 `SemiMaterial`、采购物料相关的定义 |

## 字段说明（补充）

- **系列**（`semi_material.series` / `product.series`，可空）：成品、半成品、采购物料（`kind=material`）均在表单或导入中可维护；用于库存结存查询按系列筛选与结果列展示（与 [inventory.md](inventory.md) 结存查询一节一致）。**`SemiMaterial.kind` 仅由菜单入口与 URL 决定**，与系列列内容无关。

## Excel 导入与「系列」列

- **成品**（`app/main/routes_product.py`）：模板第 6 列「系列」写入 `product.series`。
- **半成品**（`app/main/routes_semi_material.py`）：模板第 6 列「系列」写入 `semi_material.series`。
- **采购物料**（`app/main/routes_procurement.py`）：模板第 6 列「系列」写入 `semi_material.series`（`kind=material`）。
- 历史：`nav_type` 曾用于「类型」内部分类，已由 `scripts/sql/run_88_product_semi_drop_nav_type.sql` 删除列；新库见 `00_full_schema.sql`。

## 关联

- 库存台账支持 `material_id`（见 [inventory.md](inventory.md)）；采购域维护物料清单（见 [procurement.md](procurement.md)）。
