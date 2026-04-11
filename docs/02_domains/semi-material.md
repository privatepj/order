# 业务域：半成品 / 物料主数据

> 本文档为**骨架**。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_semi_material.py` |
| 模板 | `app/templates/semi_material/*.html` |
| 模型 | `app/models/` 中与 `SemiMaterial`、采购物料相关的定义 |

## 关联

- 库存台账支持 `material_id`（见 [inventory.md](inventory.md)）；采购域维护物料清单（见 [procurement.md](procurement.md)）。
