# 2026-04-16：供应商 Excel 批量导入（主数据+映射）

## 摘要
新增“供应商管理”的 Excel 批量导入能力，可一次性导入供应商主数据与供应商-物料映射（最近单价/备注/默认标记）。
导入语义为 upsert-only：只新增/更新 Excel 中出现的映射，不删除库中其它已有映射。

## 影响范围
- 域：order / procurement
- 模块：`app/main/routes_procurement.py`、`app/templates/procurement/`

## 代码变更（要点）
- `procurement/suppliers/export-import-template`：提供供应商导入模板下载（表头固定，支持从第 2 行开始填数据）。
- `procurement/suppliers/import`：上传并导入 Excel；按“供应商名称”分组创建/更新 `Supplier`，并对 `SupplierMaterialMap` 执行 upsert-only。
- upsert-only 默认供应商语义复用原逻辑：当某供应商-物料被标记为默认时，会清理同一物料下其它默认供应商。
- 新增单测覆盖 upsert-only“不删除其它映射”与“默认供应商切换清理其它默认标记”。

## 文档 / Skill 同步
- [ ] `docs/02_domains/procurement.md`
- [ ] `docs/04_ai/project-skill/SKILL.md`

## SQL / 迁移
- 新增：否（仅新增/修改应用层功能，无需 schema 变更）
- `00_full_schema.sql`：否已对齐（本次不涉及 SQL）

## 验证
- 测试：`pytest tests/test_procurement_supplier_import.py`
- 手工验收：在“供应商管理”页点击“Excel 导入”，下载模板后上传，确认映射更新且不删除其它物料映射。

