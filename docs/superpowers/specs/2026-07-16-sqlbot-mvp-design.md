# SQLbot MVP 设计

**日期：** 2026-07-16  
**状态：** 已确认，待审阅

## 1. 目标与范围

在本目录创建一个可本地运行的 SQLbot 最小可行产品。用户在网页中输入中文自然语言问题，系统基于内置 SQLite 电商示例库生成 SQL；用户确认或编辑 SQL 后，系统执行安全的只读查询并展示结果。

MVP 的目标是验证完整链路：

```text
自然语言问题 → OpenAI 兼容模型生成 SQL → 用户确认 → SQLite 查询 → 表格结果
```

### 1.1 本期包含

- FastAPI Web 应用与单页原生前端。
- OpenAI Chat Completions 兼容的模型服务连接。
- 前端输入并通过 localStorage 保存以下配置：
  - API Base URL
  - API Key
  - 模型名称
- 内置 SQLite 电商示例数据：`customers`、`products`、`orders`、`order_items`。
- 根据实际 SQLite Schema 生成模型提示词。
- 生成并展示可编辑 SQL，不自动执行。
- 仅允许单条只读 `SELECT` 或 `WITH ... SELECT` 查询。
- 查询结果表格、空结果和错误状态。
- 后端 SQL 防护与自动化测试。

### 1.2 本期不包含

- 多数据库连接（MySQL、PostgreSQL 等）。
- SQLite 文件上传或连接用户的真实数据库。
- 写操作、DDL、事务或存储过程。
- 登录、用户账户、服务端持久化配置。
- 多轮会话记忆、查询历史、权限管理或生产部署。
- 自动执行模型生成的 SQL。

## 2. 技术选择

| 层 | 选择 | 原因 |
| --- | --- | --- |
| 后端 | Python + FastAPI | SQLite 集成简单，路由、校验和测试支持成熟。 |
| 前端 | 原生 HTML、CSS、JavaScript | MVP 依赖少，单页交互足够，后续可替换为独立前端。 |
| 数据库 | SQLite | 无需安装外部服务，便于预置数据和端到端测试。 |
| 模型接口 | OpenAI Chat Completions 兼容 HTTP API | 可接 OpenAI 或同协议的第三方、本地网关。 |
| 配置存储 | 浏览器 localStorage | 刷新后保持开发配置；服务端不落盘密钥。 |

采用单体 FastAPI Web 应用：后端同时提供 JSON API 和静态文件，不拆分独立前端工程。

## 3. 系统架构

```text
┌──────────────────────────────────────────────────────┐
│ 浏览器                                                 │
│  设置面板（localStorage）                              │
│  自然语言输入 → SQL 编辑/确认 → 结果表格               │
└───────────────────┬──────────────────────────────────┘
                    │ HTTP
┌───────────────────▼──────────────────────────────────┐
│ FastAPI                                               │
│  POST /api/generate-sql                               │
│    Schema Reader → Prompt Builder → OpenAI 兼容 API   │
│    → SQL 提取与校验                                   │
│                                                       │
│  POST /api/execute-sql                                │
│    SQL Guard → SQLite 只读执行 → 结果格式化           │
└───────────────────┬──────────────────────────────────┘
                    │
┌───────────────────▼──────────────────────────────────┐
│ data/demo.db                                          │
│ customers / products / orders / order_items            │
└──────────────────────────────────────────────────────┘
```

### 3.1 信任边界

- 模型只生成文本，不能直接访问数据库。
- 浏览器提交的 SQL 与模型返回的 SQL 同样不可信。
- 后端是唯一可以访问 SQLite 和执行 SQL 的位置。
- 生成和执行接口都必须调用 SQL Guard。
- API Key 只从浏览器请求中临时转发，不能写入日志、响应、数据库或项目文件。

## 4. 项目结构

```text
SQLbot/
├─ app/
│  ├─ main.py              # FastAPI 应用、路由注册、静态文件
│  ├─ api/
│  │  ├─ schemas.py        # Pydantic 请求与响应模型
│  │  └─ routes.py         # 生成 SQL、执行 SQL 的端点
│  ├─ services/
│  │  ├─ llm_client.py     # OpenAI 兼容 Chat Completions 调用
│  │  ├─ schema_reader.py  # SQLite Schema 的读取与文本格式化
│  │  ├─ sql_guard.py      # 单语句和只读 SQL 防护
│  │  └─ query_executor.py # 受限 SQLite 查询执行与结果格式化
│  ├─ database/
│  │  └─ seed.py           # 示例数据库与种子数据创建
│  └─ static/
│     ├─ index.html
│     ├─ app.js
│     └─ styles.css
├─ data/
│  └─ demo.db              # 首次启动时自动创建
├─ tests/
│  ├─ test_sql_guard.py
│  ├─ test_query_executor.py
│  └─ test_api.py
├─ requirements.txt
├─ .env.example
└─ README.md
```

## 5. 数据库设计

内置电商分析数据库，为自然语言转 SQL 提供可理解的关联关系和聚合场景。

### 5.1 表

- `customers`：客户基础信息。
- `products`：商品基础信息和单价。
- `orders`：订单主表，关联客户，包含订单状态、日期和订单总额。
- `order_items`：订单明细，关联订单与商品，包含购买数量和成交单价。

示例数据覆盖客户、商品、订单、订单明细及多个日期范围，支持以下典型提问：

- “消费金额最高的 10 位客户”。
- “销量最高的 5 个商品”。
- “按月统计已完成订单的销售额”。
- “哪些客户没有下过订单”。

## 6. API 设计

### 6.1 `POST /api/generate-sql`

将自然语言问题转换为 SQL，并在返回前进行安全校验。

请求：

```json
{
  "question": "查询消费金额最高的 10 位客户",
  "provider": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-...",
    "model": "gpt-4.1-mini"
  }
}
```

成功响应：

```json
{
  "sql": "SELECT c.name, SUM(o.total_amount) AS total_spend ...",
  "schema_summary": "customers, products, orders, order_items",
  "message": "SQL 已生成，请确认后执行。"
}
```

失败响应使用结构化 HTTP 4xx/5xx 错误。模型服务异常必须转化为可理解的错误信息，且不包含 API Key、服务器路径或内部堆栈。

### 6.2 `POST /api/execute-sql`

执行经用户确认或编辑后的 SQL。该端点不接受 Provider 配置。

请求：

```json
{
  "sql": "SELECT name, email FROM customers LIMIT 10"
}
```

成功响应：

```json
{
  "columns": ["name", "email"],
  "rows": [["张三", "zhangsan@example.com"]],
  "row_count": 1,
  "truncated": false
}
```

`row_count` 为实际返回行数；当后端截断结果时，`truncated` 为 `true`，并明确提示用户只显示前 200 行。

## 7. 生成 SQL 的提示词策略

后端在每次请求时读取当前 SQLite 的表结构、字段和关联关系，并将其放入系统提示词。模型约束如下：

1. 只返回一条可由 SQLite 执行的 SQL。
2. 只允许 `SELECT` 或 `WITH ... SELECT`。
3. 只能引用给定 Schema 中存在的表与字段。
4. 不得返回解释、Markdown、代码块或其他文本。
5. 对可能返回很多行的查询优先加入合理 `LIMIT`。

模型输出仍被视为不可信：后端需要去除常见 Markdown 包装、提取 SQL 并交给 SQL Guard 校验。

## 8. SQL 安全策略

### 8.1 允许范围

- 仅单条 `SELECT ...`。
- 仅单条以 `WITH` 开始并最终返回查询结果的 CTE 查询。
- 末尾最多一个分号。

### 8.2 禁止范围

拒绝下列任意语句、关键字或执行模式：

- 数据变更：`INSERT`、`UPDATE`、`DELETE`、`REPLACE`。
- 数据定义：`CREATE`、`DROP`、`ALTER`、`VACUUM`。
- SQLite 管理/外部访问：`PRAGMA`、`ATTACH`、`DETACH`、`LOAD_EXTENSION`。
- 事务控制：`BEGIN`、`COMMIT`、`ROLLBACK`、`SAVEPOINT`、`RELEASE`。
- 多条有效 SQL 语句。

### 8.3 执行限制

- 连接 SQLite 时启用只读模式。
- 结果集最多返回 200 行。
- 执行前后均使用 SQL Guard：生成端点可阻止不安全模型输出；执行端点可阻止客户端绕过页面或手工修改 SQL。
- 将数据库异常映射为安全、可理解的业务错误，不暴露文件系统细节。

## 9. 页面行为

### 9.1 设置面板

- 包含 API Base URL、API Key 和模型名称。
- API Key 使用密码输入框。
- “保存设置”存到 localStorage。
- “清除配置”删除 localStorage 内该应用的设置。
- 页面提示：localStorage 仅适合本机开发；不要在多人共用或生产环境保存真实 API Key。

### 9.2 查询流程

1. 用户输入自然语言问题并点击“生成 SQL”。
2. 生成期间显示加载状态并禁用重复提交。
3. 成功后将 SQL 放入可编辑文本区；不自动执行。
4. 用户可复制、编辑，或点击“执行查询”。
5. 查询结果以表格显示，包含行数、空状态和截断提示。

### 9.3 错误处理

- 不自动重试模型请求。
- 不用示例 SQL 冒充模型输出。
- 服务错误、生成错误、SQL Guard 拒绝和执行错误都显示明确反馈。
- 出错后保留问题、Provider 设置和 SQL 编辑内容，使用户可以修正后重试。

## 10. 测试策略

测试不依赖真实 API Key 或外部模型。

### 10.1 SQL Guard 单元测试

- 允许标准 `SELECT`。
- 允许 CTE 查询。
- 拒绝写操作、DDL、事务、PRAGMA、ATTACH 与多语句。
- 拒绝空 SQL、非查询开头和不合法格式。

### 10.2 查询执行器单元测试

- 正确返回列名、行和行数。
- 对超过 200 行的结果只返回 200 行并标记截断。
- SQLite 异常被转换为预期的业务错误。

### 10.3 API 集成测试

- 执行接口的正常查询可返回表格数据。
- 非法 SQL 返回 4xx。
- 通过 mock 的模型客户端验证生成接口将 Schema 放入提示词，且对模型返回 SQL 执行校验。

## 11. MVP 验收标准

1. 启动本地应用后，浏览器可打开页面。
2. 用户可填写并保存 OpenAI 兼容服务配置。
3. 用户可输入“查询销售额最高的 5 个商品”，获得可编辑 SQL。
4. 生成 SQL 不会自动执行。
5. 点击“执行查询”后，页面展示 SQLite 结果表格。
6. 用户提交 `DELETE FROM orders`、`SELECT 1; DELETE FROM orders` 等 SQL 时，后端拒绝执行。
7. 无效 API Key、错误模型名称、网络异常或模型服务错误会显示明确错误，并保留页面内容。
8. 自动化测试无需真实模型服务即可运行并通过。

## 12. 迭代方向（不属于 MVP）

在 MVP 稳定后，可按以下顺序扩展：

1. Schema 浏览器、查询历史和示例问题。
2. 模型输出解释、SQL 高亮、查询计划和导出 CSV。
3. 多轮对话与前序查询上下文。
4. 只读 MySQL/PostgreSQL 连接器与服务器端密钥管理。
5. 用户认证、数据库授权、审计和细粒度 SQL 策略。
