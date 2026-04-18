# 业务域：半成品 / 物料主数据

> 本文档为**骨架**。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_semi_material.py` |
| 模板 | `app/templates/semi_material/*.html` |
| 模型 | `app/models/` 中与 `SemiMaterial`、采购物料相关的定义 |

## 字段说明（补充）

- **系列**（`semi_material.series`，可空）：仅**半成品**（`kind=semi`）在表单/导入中维护；用于库存结存查询按系列筛选（与成品 `product.series` 一并出现在下拉选项中，见 [inventory.md](inventory.md) 结存查询一节）。
- **类型**（`semi_material.nav_type` / `product.nav_type`，可空）：主数据**内部分类/导航**，与「成品 vs 半成品 vs 采购物料」主数据类别无关；列表关键字搜索会匹配该字段。成品用 `product.nav_type`；半成品与采购物料均用 `semi_material.nav_type`（采购物料表单在采购域维护）。

## Excel 导入与「类型」列

- **成品**（`app/main/routes_product.py`）：模板与导入第 7 列「类型」写入 `product.nav_type`（内部分类）；导入流程始终是成品主数据。
- **半成品/采购物料**（`app/main/routes_semi_material.py`）：第 7 列写入 `semi_material.nav_type`。**`SemiMaterial.kind`（半成品/采购物料）仅由菜单入口与 URL 决定**，与「类型」列无关。
- 库表增量：`scripts/sql/run_87_product_semi_nav_type.sql`。

## 关联

- 库存台账支持 `material_id`（见 [inventory.md](inventory.md)）；采购域维护物料清单（见 [procurement.md](procurement.md)）。
