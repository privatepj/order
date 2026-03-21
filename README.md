# 工厂订单系统 (sydixon-order)

用于管理客户下单、送货与月底对账的 Web 系统，支持订单表头+多行明细、一次送货多张订单、按客户与月份导出对账单 Excel。

## 技术栈

- **后端**：Python 3.8+，Flask，Flask-Login，Flask-SQLAlchemy，PyMySQL，bcrypt，openpyxl
- **前端**：Jinja2 模板 + Bootstrap 5
- **数据库**：MySQL 5.7 / 8.0

## 本地开发

1. 创建虚拟环境并安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

2. 创建数据库并执行初始化脚本（见 [项目整体部署.md](项目整体部署.md) 第 3 节）。**若库已存在旧结构**，请先执行 `scripts/migrate_v2_company_customer.sql`，再执行 `scripts/migrate_company_order_no.sql`（公司主体订单号前缀与转月日），再执行 `scripts/migrate_express_delivery.sql`（快递公司、单号池、送货单扩展、送货单号前缀），然后启动应用。

3. 复制 `.env.example` 为 `.env`，填写 `DATABASE_URL` 和 `SECRET_KEY`。

4. 启动：

   ```bash
   python run.py
   ```

5. 浏览器访问 http://127.0.0.1:5000 ，使用默认账号 `admin` / 密码 `password` 登录（请首次登录后修改密码）。

## 功能概览

- **客户**：客户列表、新增/编辑/删除
- **订单**：订单列表（按客户/状态筛选）、新增订单；编辑/删除仅管理员；订单号按公司主体规则生成；订单详情（每行已送/未送数量）
- **公司主体**（管理员）：维护订单号前缀、送货单号前缀、转月日
- **快递**（管理员）：快递公司、批量录入单号（起止区间自动补全）
- **送货**：送货单号按主体+日期+业务月序号；选快递并自动带出可用单号；列表/详情展示快递单号
- **对账导出**：选择客户与年月，生成对账单 Excel 并下载

## 部署

详见 [项目整体部署.md](项目整体部署.md)，包含环境要求、数据库初始化、环境变量、gunicorn 运行、Nginx 与 systemd 可选配置，以及首次登录说明。

## 项目结构

```
app/
  __init__.py      # Flask 应用工厂、Flask-Login
  config.py        # 配置
  models/          # 数据模型（用户、客户、订单、送货）
  auth/            # 登录、登出、权限装饰器
  main/            # 客户/订单/送货/对账路由
  templates/       # Jinja2 模板
  static/          # 静态资源
scripts/
  init_db.sql                    # MySQL 建表与初始数据（含经营主体、客户税点等）
  migrate_v2_company_customer.sql # 已有库升级：公司表、客户 company_id/tax_point、客户产品 material_no
  migrate_company_order_no.sql    # 公司表 order_no_prefix、billing_cycle_day
  migrate_express_delivery.sql    # 快递公司与单号池、送货单快递字段、公司 delivery_no_prefix
run.py             # 启动入口
requirements.txt
.env.example
项目整体部署.md
```
