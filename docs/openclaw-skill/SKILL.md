---
name: sydixon-order
description: 工厂订单与送货单。下单并送货=同一条助手消息内输出订单表+送货表，用户只确认一次「确认执行」后连续 POST 订单与 POST 送货，禁止订单与送货各问一次确认。仅下单不送货才可只确认订单。客户简称；K=1000；默认今天、顺丰。
requires:
  env:
    - SYDIXON_ORDER_URL
    - SYDIXON_ORDER_API_KEY
  bins:
    - curl
    - jq
---

# Sydixon 订单 / 送货单技能（输入确认制度）

当用户说「给 XX 客户送 50K A产品」「给客户 A 下单」「做一张送货单」等时使用本技能。

## 先分流：两种模式（必看）

| 用户意图 | 确认次数 | 做法 |
|----------|----------|------|
| **下单并送货**（同一对话里既要订单又要送货单） | **整笔业务只允许 1 次**用户说「确认执行」 | 必须先走下方 **「订单 + 送货双表一步确认」**：同一条消息里给出表 1 + 表 2，用户确认后**连续** `POST orders` → `GET pending-items` → `POST deliveries/preview` → `POST deliveries`，**不得**在订单写好后再问「是否确认送货」。 |
| **仅下单**或**仅做送货单** | 可针对该单步确认一次 | 只执行阶段 C（或只执行阶段 D），按该阶段说明即可。 |

**反模式（禁止）**：先展示订单预览并让用户确认 → 建订单 → 再展示送货预览并让用户再确认。除非用户明确只要下单、不要送货。

## 硬性规则（违反即视为错误用法）

1. **收到用户第一句需求后**，必须先输出**整体流程草图**。**下单并送货**时草图须体现：**查客户 → 若无则建客户 → 查/建客户产品（含单价）→ 双表一步确认（订单表+送货计划表）→ 依次建订单 → 核对送货预览 → 建送货单**。**不得**立刻调用 `POST .../orders` 或 `POST .../deliveries`。
2. **在用户明确确认之前**，禁止调用任何**写库**接口：
   - 禁止：`POST /api/openclaw/customers`、`POST /api/openclaw/customer-products`、`POST /api/openclaw/orders`、`POST /api/openclaw/deliveries`。
3. **允许在用户确认对应步骤之后**再调用的写接口见下文各节；**预览接口**（不写库）可在展示摘要前随时调用。**下单并送货**时，订单预览与送货计划必须在**同一次**用户确认之前全部展示完毕（双表），**不得**用「先确认订单预览、再确认送货预览」拆成两次人工确认。
4. **确认用语**：执行写操作前，用户须给出明确指令，例如包含 **「确认执行」** 或 **「确认创建」**。若用户需要**下单并送货**，须在同一轮对话中完成「双表一步确认」（见下文），**禁止**先让用户确认订单、再单独让用户确认送货（除非用户明确只要下单、不送货）。含糊的「好」「行」若上下文不清，应再次复述要点并请用户说「确认执行」。
5. **编号**：订单号、送货单号、运单占号均由**服务端**生成；请求体**不得**自拟 `order_no`、`delivery_no`；成功以后端返回为准。
6. **产品候选展示**：`GET .../products` 返回的 `name`、`spec`、`remark` 均来自数据库主数据；若多行名称/规格看似相同，须用 **`id` + `product_code` + `remark`** 区分并请用户点名确认。若与实物不符，应在系统中修正 `product` 表，而非归咎于接口。
7. **⚠️ 关键：确认表格中必须显示完整产品名**：`POST .../orders/preview` 返回的 `product_name`（完整系统名称，如"双面A公橙胶夹板焊GB-01五芯 MT888+5.1K"）**必须原样展示**，禁止截断或用用户简称替代。确认双表时产品列必须显示产品编码 + 完整名称（如 `XDS.0201 - 双面A公橙胶夹板焊GB-01五芯 MT888+5.1K`），确保用户能识别是否选错产品。

## 约定

- **客户**：对话中用简称；`GET .../api/openclaw/customers?q=` **必填**，`q` 至少 **2** 个字符（按简称/编码模糊匹配）；缺省、过短或仅空白时返回 **HTTP 400**（`{"ok":false,"error":"..."}`），**禁止**用空 `q` 拉列表。成功时仅返回 `id` 与 `label`（简称），不展示完整企业名。
- **隐私**：OpenClaw **任意接口**的 JSON **响应**中均不包含客户联系人、联系人手机号；不要在总结中引用或编造这些字段。新建客户时若请求体包含 `contact`、`phone`，为落库用途，**成功响应仍只含** `ok`、`customer_id`、`customer_code`、`label`（简称），不回显联系方式。
- **数量**：**K = 1000**（50K = 50000）。
- **送货**：默认**今天**、默认**顺丰**；多单默认 **FIFO**；用户指定订单时用 `order_id` 约束（见送货接口）。
- **能力**：用户令牌需在角色中勾选对应 `openclaw.*` 细项；缺能力会返回 HTTP 403。
- **编码**：请求须使用 **UTF-8** JSON；`Content-Type` 建议 `application/json; charset=utf-8`。服务端数据库须 **utf8mb4**（见部署 `DATABASE_URL`）。否则中文客户名等可能变为乱码或问号。

## 鉴权

`X-API-Key: $SYDIXON_ORDER_API_KEY` 或 `Authorization: Bearer $SYDIXON_ORDER_API_KEY`（可为全局 Key 或 `flask openclaw-token-create` 生成的 `oc_` 令牌）。

---

## 阶段 A：流程说明与客户

用户提出需求后：

1. 用一段话列出拟执行步骤（见硬性规则 1）。
2. `GET .../api/openclaw/customers?q=简称` 检索客户（`q` 至少 2 个字符，见「约定」）。

**若客户不存在**（或用户要求新建）：

- 向用户收集并**复述确认**后再执行创建：
  - **必填**：客户全称 `name`、**经营主体** `company_id`（先 `GET .../api/openclaw/companies` 列出 `id/code/name` 供选择）。
  - **强烈建议**：联系人 `contact`、电话 `phone`；可选：`short_code`、`address`、`payment_terms`、`remark`、`tax_point`。
- 用户确认后：`POST .../api/openclaw/customers`，Body 为 JSON（字段名与接口一致）。

**若客户已存在**：记录 `customer_id`，进入阶段 B。

---

## 阶段 B：客户产品

`GET .../api/openclaw/customer-products?customer_id=&q=` 查是否已有绑定。

**若不存在**：

1. `GET .../api/openclaw/products?q=` 搜索系统产品；向用户展示候选时**必须使用 Markdown 表格**，列至少含 **`id`、`product_code`、`name`、`spec`、`remark`**（`remark` 常含颜色等补充信息），表格中产品名称列显示**完整名称**，**请用户确认**唯一 `product_id`。不得仅凭规格简称（如「3D-A」）在未展示编码与 `id` 时让用户猜选。
2. **必须**向用户确认并写入复述清单：**单价 `price`、币种 `currency`**（与 Web 一致）；未确认单价不得进入后续下单。
3. 用户确认后：`POST .../api/openclaw/customer-products`，Body 含 `customer_id`、`product_id`，以及确认后的 `price`、`currency`（及可选 `unit`、`customer_material_no` 等）。**物料编号与产品 `product_code` 一致，勿单独传 `material_no`（服务端会忽略并写入产品编号）。**具备 `openclaw.customer_product.create` 的令牌可写单价/币种；若接口返回成功但此前未传单价，说明未满足业务要求，应回到用户处补全并重试。

**若已存在**：选定 `customer_product_id`，进入阶段 C。

---

## 阶段 C：订单（必须先预览再创建）

1. **必填信息**（缺一则不得进入最终「确认执行」）：
   - **`customer_order_no`**：客户订单编号（OpenClaw `POST .../orders` 必填，空则 400）。
   - **`payment_type`**：`monthly`（月结）或 `cash`（现金）；须向用户**问清**二选一，不得静默默认。
2. 组装与正式建单**相同**的 JSON body：`customer_id`、`customer_order_no`、`payment_type`、`items`: `[{ customer_product_id, quantity, is_sample? }]`，及其他可选字段（`salesperson`、`order_date`、`required_date`、`remark` 等）。
3. **先** `POST .../api/openclaw/orders/preview`，得到 `summary`（用于展示，含 `customer_order_no`、`payment_type_label`、`order_no_note`、各行数量与单价/金额等）。

**与阶段 D 的衔接（关键）**：

- **若用户要「下单并送货」**：**不要**在本阶段单独让用户说「确认执行」也**不要**在本阶段 `POST .../orders`。应带着本 `summary` 去构造 **「双表一步确认」**里的表 1，并同时给出表 2（送货计划）；**仅当**用户对双表说过一次「确认执行」后，才执行 `POST .../orders` 及后续送货链路（见专节）。
- **若用户只要下单、不要送货**：用户确认订单内容后，**再** `POST .../api/openclaw/orders`（与预览 **相同 body**）。成功响应含 `order_id`、`order_no`。

---

## 阶段 D：送货单（必须先预览再创建）

1. `GET .../api/openclaw/deliveries/pending-items?customer_id=`（可选 `order_id=`）取得待发 `order_item_id`；响应含 `quantity`、`delivered_qty`、`in_transit_qty`、`remaining_qty`（均为**十进制字符串**，避免 IEEE754；解析比较请用 Decimal）。组装 `lines` 时本次数量不得超过 `remaining_qty`。
2. 组装 `lines`：`[{ order_item_id, quantity }]`；若指定订单，body 加 `order_id` 与接口说明一致。
3. `POST .../api/openclaw/deliveries/preview` 得到 `summary`（日期、是否自配送、快递、各行）。

**与确认次数的衔接**：

- **若用户要「下单并送货」**：送货 `summary` 已在用户**唯一一次**「确认执行」之前，作为 **表 2** 与用户见过面；用户确认后依次 `POST orders` → `GET pending-items` → `POST deliveries/preview`（与表 2 核对）→ `POST deliveries`，**此间不得再向用户要第二次确认**。
- **若用户只要新建送货单**（订单已存在）：可单独展示送货预览，用户确认后再 `POST .../deliveries`。

---

## 订单 + 送货「双表一步确认」（对话层）

当用户意图为「下单并送货」时（**本节优先级高于阶段 C/D 里「逐步确认」的字面顺序**）：

1. 在调用任何写库接口前，在**同一条助手消息**内输出 **两个 Markdown 表格**（缺一不可）：
   - **表 1（订单）**：基于 `POST .../orders/preview` 的 `summary`，**产品列必须显示 `product_code` + 完整 `product_name`**（禁止截断或用简称）。至少含：客户简称、`customer_order_no`、付款方式（`payment_type_label`）、各行产品（编码+全名）/数量、单价/金额等。
   - **表 2（送货计划）**：送货日期、是否自配送、快递公司、**各行本次送货数量**；产品列必须与表 1 一致，显示编码+全名；若尚无 `order_item_id`，列中可用与表 1 对齐的 **产品编码 / 完整名称** 描述，并注明「保存订单后由 `pending-items` 匹配 `order_item_id`」。
2. 用户仅对上述双表回复 **一次**「确认执行」后，Agent **连续**执行，**中间不得再向用户索要第二次确认**：
   - `POST .../orders`（与表 1 / 预览 body 一致）；
   - `GET .../deliveries/pending-items`（可用 `order_id` 过滤）；
   - `POST .../deliveries/preview`，与表 2 核对；
   - 一致则 `POST .../deliveries`；不一致则**中止**并说明差异（不得擅自改数）。
3. **禁止**拆成「先确认订单表 → 建单 → 再确认送货表」两步人工确认（除非用户只要下单、不送货）。

仅下单、不送货时，可只展示表 1 并确认，不执行阶段 D 的写接口。

---

## 接口速查（curl 示例）

以下示例均使用 UTF-8；请求头建议带 `charset=utf-8`。

**经营主体（新建客户前）**

```bash
curl -s -H "X-API-Key: $SYDIXON_ORDER_API_KEY" "$SYDIXON_ORDER_URL/api/openclaw/companies"
```

**系统产品搜索**

```bash
curl -s -H "X-API-Key: $SYDIXON_ORDER_API_KEY" "$SYDIXON_ORDER_URL/api/openclaw/products?q=关键词&limit=50"
```

**客户搜索（q 必填，至少 2 字符）**

```bash
curl -s -H "X-API-Key: $SYDIXON_ORDER_API_KEY" "$SYDIXON_ORDER_URL/api/openclaw/customers?q=简称&limit=20"
```

**新建客户（仅确认后）**

```bash
curl -s -X POST -H "Content-Type: application/json; charset=utf-8" -H "X-API-Key: $SYDIXON_ORDER_API_KEY" \
  -d '{"name":"客户全称","company_id":1,"contact":"张三","phone":"13800000000","short_code":"简称"}' \
  "$SYDIXON_ORDER_URL/api/openclaw/customers"
```

**新建客户产品（仅确认后，含单价）**

```bash
curl -s -X POST -H "Content-Type: application/json; charset=utf-8" -H "X-API-Key: $SYDIXON_ORDER_API_KEY" \
  -d '{"customer_id":1,"product_id":10,"price":"12.50","currency":"CNY"}' \
  "$SYDIXON_ORDER_URL/api/openclaw/customer-products"
```

**订单预览 / 创建**

```bash
curl -s -X POST -H "Content-Type: application/json; charset=utf-8" -H "X-API-Key: $SYDIXON_ORDER_API_KEY" \
  -d '{"customer_id":1,"customer_order_no":"PO-2026-001","payment_type":"monthly","items":[{"customer_product_id":20,"quantity":50000,"is_sample":false}]}' \
  "$SYDIXON_ORDER_URL/api/openclaw/orders/preview"
# 用户确认后再 POST .../orders 相同 body
```

**送货预览 / 创建**

```bash
curl -s -X POST -H "Content-Type: application/json; charset=utf-8" -H "X-API-Key: $SYDIXON_ORDER_API_KEY" \
  -d '{"customer_id":1,"lines":[{"order_item_id":101,"quantity":50000}]}' \
  "$SYDIXON_ORDER_URL/api/openclaw/deliveries/preview"
```

其余 `GET customer-products`、`GET pending-items` 等与上文一致；`GET customers` 见上（`q` 必填）。

---

## 错误与限流

- 业务校验失败（含客户搜索缺少/过短 `q`）：`{"ok":false,"error":"..."}`，HTTP **400**。
- 未授权/无能力：**401** / **403**。
- 频率限制：**429**（见部署说明 `OPENCLAW_RATE_LIMIT_PER_MINUTE`）。

将 `error` 转为自然语言告知用户；**不要**在未确认时重试写接口。
