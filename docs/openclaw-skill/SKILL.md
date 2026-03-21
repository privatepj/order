---
name: sydixon-order
description: 工厂订单与送货单管理。通过对话给指定客户下单、创建送货单；客户用简称指代，不确定时列出候选选择；数量单位 K=1000；默认今天送货、默认顺丰；多单 FIFO 或指定订单。
requires:
  env:
    - SYDIXON_ORDER_URL
    - SYDIXON_ORDER_API_KEY
  bins:
    - curl
    - jq
---

# Sydixon 订单 / 送货单技能

当用户说「给 XX 客户送 50K A产品」「给客户 A 下单」「做一张送货单」等时使用本技能。

## 约定

- **客户**：一律用**简称**指代；解析不确定时调用客户接口得到**仅含简称的候选列表**供用户选择，不展示完整客户信息。
- **数量**：**K = 1000**（如 50K = 50000）。
- **送货单**：默认**今天**、默认**顺丰**；多张订单时默认 **FIFO**，用户可说「从订单 XXX 送」则只从该单送。
- **数量不足**：待送总量小于用户要送的数量时，先新开订单补足再创建送货单。

## 接口 Base URL 与鉴权

- Base URL：环境变量 `SYDIXON_ORDER_URL`（如 `http://127.0.0.1:5000`）。
- 请求头：`X-API-Key: $SYDIXON_ORDER_API_KEY` 或 `Authorization: Bearer $SYDIXON_ORDER_API_KEY`。

## 1. 解析客户

用户说「给 XX 送」时，用简称 `XX` 查询客户：

```bash
curl -s -H "X-API-Key: $SYDIXON_ORDER_API_KEY" "$SYDIXON_ORDER_URL/api/openclaw/customers?q=XX&limit=20"
```

响应示例：`{"items":[{"id":1,"label":"A公司"},{"id":2,"label":"A2"}]}`。若多条，列出 `label` 供用户选择，得到 `customer_id`。

## 2. 解析产品（客户产品）

根据用户说的产品名/编码，查询该客户的客户产品：

```bash
curl -s -H "X-API-Key: $SYDIXON_ORDER_API_KEY" "$SYDIXON_ORDER_URL/api/openclaw/customer-products?customer_id=1&q=产品名或编码&limit=50"
```

响应示例：`{"items":[{"id":10,"product_code":"P001","product_name":"A产品","product_spec":"规格",...}]}`。取匹配的 `id` 作为 `customer_product_id`。

## 3. 待发货明细（做送货单前）

获取该客户待发货订单行（可选指定订单号，实现「从订单 XXX 送」）：

```bash
# 全部待发（FIFO 时用）
curl -s -H "X-API-Key: $SYDIXON_ORDER_API_KEY" "$SYDIXON_ORDER_URL/api/openclaw/deliveries/pending-items?customer_id=1"
# 指定订单
curl -s -H "X-API-Key: $SYDIXON_ORDER_API_KEY" "$SYDIXON_ORDER_URL/api/openclaw/deliveries/pending-items?customer_id=1&order_id=123"
```

响应示例：`{"items":[{"order_item_id":101,"order_id":12,"order_no":"SO0319001","product_name":"A产品","quantity":100,"remaining_qty":50,...}]}`。按 FIFO 或指定订单选行，用 `order_item_id` 与用户说的数量组成 `lines`。

## 4. 创建订单

当该客户该产品**没有在途订单**或需要**新开订单**时：

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: $SYDIXON_ORDER_API_KEY" \
  -d '{"customer_id":1,"items":[{"customer_product_id":10,"quantity":50000,"is_sample":false}]}' \
  "$SYDIXON_ORDER_URL/api/openclaw/orders"
```

Body 可选：`customer_order_no`, `salesperson`, `order_date`, `required_date`, `payment_type`, `remark`。数量用整数（50K 即 50000）。

成功响应：`{"ok":true,"order_id":123,"order_no":"SO0319001"}`。

## 5. 创建送货单

用选好的待发订单行和数量组 `lines`，默认今天、顺丰（可不传 `express_company_id`、`delivery_date`）：

```bash
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: $SYDIXON_ORDER_API_KEY" \
  -d '{"customer_id":1,"lines":[{"order_item_id":101,"quantity":50000}]}' \
  "$SYDIXON_ORDER_URL/api/openclaw/deliveries"
```

可选 Body：`express_company_id`, `delivery_date`（如 `2026-03-20`）, `driver`, `plate_no`, `remark`。

成功响应：`{"ok":true,"delivery_id":456,"delivery_no":"DL202603190001","waybill_no":"SF1234567890"}`。

## 典型流程：「给 XX 客户送 50K A产品」

1. `GET /api/openclaw/customers?q=XX` → 得到 `customer_id`（多候选则让用户选）。
2. `GET /api/openclaw/deliveries/pending-items?customer_id=<id>` → 看是否有 A 产品的待发行。
3. **若无待发**：`GET /api/openclaw/customer-products?customer_id=<id>&q=A` → 得 `customer_product_id`；`POST /api/openclaw/orders` 建单；再 `GET pending-items` 取新订单行；再 `POST /api/openclaw/deliveries`。
4. **若有待发**：按 FIFO（或用户指定订单）选行，若剩余量 ≥ 50K 则组一条 `{order_item_id, quantity: 50000}`；若不足则新开订单补足后再建送货单。最后 `POST /api/openclaw/deliveries`。
5. 回复用户：「已为 XX 创建送货单 DL202603190001，运单号 SF1234567890。」

## 错误响应

接口失败时返回 JSON：`{"ok":false,"error":"错误说明"}`，HTTP 4xx。将 `error` 转成自然语言回复用户。
