# SQLbot MVP 实现计划（中文版）

> **面向智能体执行者：** 必须按任务逐项执行；推荐使用 `superpowers:subagent-driven-development`，也可以使用 `superpowers:executing-plans`。每一步均使用复选框（`- [ ]`）跟踪。
>
> **英文原版：** [2026-07-16-sqlbot-mvp-implementation.md](2026-07-16-sqlbot-mvp-implementation.md)。两份计划的任务顺序、文件路径、接口和命令一致；本文件用于中文审阅与执行。代码标识符、接口字段和提交命令保持英文，避免翻译造成实现偏差。

**目标：** 构建一个可本地运行的 FastAPI Web 应用：用户输入自然语言问题，通过 OpenAI Chat Completions 兼容接口生成 SQL，确认后以只读方式查询内置 SQLite 示例数据库。

**架构：** 单个 FastAPI 进程同时提供静态单页网页和两个 JSON API。LLM 适配层仅生成 SQL 文本；无论 SQL 来自模型还是用户手动编辑，均须经过共享的只读 SQL Guard，并由具备 SQLite authorizer 防护的执行器在示例数据库中执行。

**技术栈：** Python 3.11+、FastAPI、Uvicorn、Pydantic v2、HTTPX、SQLite（`sqlite3`）、pytest、Starlette TestClient、HTML/CSS/原生 JavaScript。

## 全局约束

- 仅支持 **OpenAI Chat Completions 兼容**接口；MVP 不接入 Anthropic 专属 Provider。
- API Base URL、API Key 与模型名称保存在浏览器 `localStorage`；不得写入服务端日志、响应、SQLite、源代码或 `.env` 文件。
- UI 与 API 通过同源 FastAPI 服务提供；不添加 CORS middleware。
- 仅使用 `data/demo.db`，并在其中创建 `customers`、`products`、`orders`、`order_items` 四张表。
- 生成 SQL 后不得自动执行；必须由用户明确点击“执行查询”。
- 仅允许单条只读 `SELECT` 或 `WITH ... SELECT`；拒绝写操作、DDL、SQLite 管理语句、事务控制和多语句。
- 在 SQL 文本校验前和 SQLite 实际执行时都执行只读限制。
- 每次查询最多返回 200 行，并明确暴露是否截断。
- 自动化测试不得依赖真实 API Key 或外部模型服务。
- 模块边界必须清晰：数据库种子、SQL 校验、Schema 读取、查询执行、LLM 传输、HTTP 路由和 UI 分别实现。

---

## 预期目录结构

```text
app/
├── __init__.py                    # Python 包标识
├── main.py                         # App 工厂、数据库初始化、静态文件挂载
├── api/
│   ├── __init__.py
│   ├── routes.py                   # /api/generate-sql 和 /api/execute-sql
│   └── schemas.py                  # Pydantic 请求/响应模型
├── database/
│   ├── __init__.py
│   └── seed.py                     # 确定性的示例 SQLite Schema 与数据
├── services/
│   ├── __init__.py
│   ├── llm_client.py               # OpenAI 兼容 Chat Completions 调用与提示词
│   ├── query_executor.py            # SQLite authorizer 与结果行限制
│   ├── schema_reader.py             # Schema 读取及模型提示词格式化
│   └── sql_guard.py                # SQL 规范化与只读安全校验
└── static/
    ├── app.js                      # 浏览器状态、API 调用、渲染、localStorage
    ├── index.html                  # 单页 HTML
    └── styles.css                  # 响应式样式

tests/
├── conftest.py                     # 测试用数据库和 FastAPI fixture
├── test_api.py                     # 使用假 LLM 的接口测试
├── test_query_executor.py          # 只读执行、截断和错误映射
├── test_seed.py                    # 种子 Schema/数据不变量
└── test_sql_guard.py               # 合法和非法 SQL 校验用例

requirements.txt
.env.example
.gitignore
README.md
```

## 任务 1：初始化 Python 项目和确定性的示例数据库

**文件：**
- 创建：`requirements.txt`
- 创建：`.gitignore`
- 创建：`.env.example`
- 创建：`app/__init__.py`
- 创建：`app/database/__init__.py`
- 创建：`app/database/seed.py`
- 创建：`tests/test_seed.py`

**接口：**
- 产出：`create_demo_database(db_path: pathlib.Path) -> None`。
- 产出：含 `customers`、`products`、`orders`、`order_items` 的确定性关联数据。

- [ ] **步骤 1：初始化 Git，以支持逐任务提交**

```bash
git init
git add docs/superpowers/specs/2026-07-16-sqlbot-mvp-design.md
git commit -m "docs: add sqlbot mvp design"
```

预期：目录成为 Git 仓库，确认过的设计文档已提交。如果 Git 缺少 `user.name` 或 `user.email`，先仅为当前仓库配置后再提交。

- [ ] **步骤 2：创建依赖与本地运行文件排除规则**

`requirements.txt`：

```text
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
httpx>=0.27,<1.0
pytest>=8.0,<9.0
```

`.gitignore`：

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
.env
data/demo.db
```

`.env.example`：

```dotenv
# This MVP receives model credentials from the browser settings panel.
# Do not put OPENAI_API_KEY in this file.
HOST=127.0.0.1
PORT=8000
```

- [ ] **步骤 3：先写失败的种子数据库测试**

在 `tests/test_seed.py` 断言：

```python
def test_seed_creates_expected_tables_and_related_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "demo.db"
    create_demo_database(db_path)

    # 断言：四张表存在；至少 6 笔 orders、8 笔 order_items；
    # orders → customers、order_items → orders/products 的联结行数等于 item 数。


def test_seed_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "demo.db"
    create_demo_database(db_path)
    create_demo_database(db_path)

    # 断言 customers 数量始终等于 5。
```

完整断言代码见英文原版“Task 1 / Step 3”，其测试输入和预期不可变更。

- [ ] **步骤 4：运行测试并确认当前失败**

```bash
python -m pytest tests/test_seed.py -v
```

预期：因 `app.database.seed` 尚不存在而在收集阶段失败。

- [ ] **步骤 5：实现 `create_demo_database`**

创建空文件 `app/__init__.py`、`app/database/__init__.py`。

在 `app/database/seed.py`：

1. 定义 `SCHEMA_SQL`，其中四张表字段为：
   - `customers(id, name, email, city, created_at)`；
   - `products(id, name, category, list_price)`；
   - `orders(id, customer_id, order_date, status, total_amount)`；
   - `order_items(id, order_id, product_id, quantity, unit_price)`。
2. `create_demo_database` 创建父目录。
3. 检查 `sqlite_master` 中是否已有 `customers`；存在则直接返回，保证幂等。
4. 使用 `executescript(SCHEMA_SQL)` 创建表。
5. 插入 5 个中文客户、5 个商品、6 笔订单、10 笔订单明细。数据需覆盖 completed、pending、cancelled 状态和 2024 年 6–8 月日期。

完整的可复制实现见英文原版“Task 1 / Step 5”。

- [ ] **步骤 6：运行种子测试并确认通过**

```bash
python -m pytest tests/test_seed.py -v
```

预期：`2 passed`。

- [ ] **步骤 7：提交**

```bash
git add requirements.txt .gitignore .env.example app tests/test_seed.py
git commit -m "feat: add seeded sqlite demo database"
```

## 任务 2：以测试驱动方式实现只读 SQL Guard

**文件：**
- 创建：`app/services/__init__.py`
- 创建：`app/services/sql_guard.py`
- 创建：`tests/test_sql_guard.py`

**接口：**
- 产出：`class SQLValidationError(ValueError)`。
- 产出：`validate_readonly_sql(sql: str) -> str`：返回移除末尾分号的单条只读 SQL，或抛出 `SQLValidationError`。

- [ ] **步骤 1：编写失败测试**

测试必须覆盖：

```python
# 允许：
validate_readonly_sql("SELECT id, name FROM customers;")
validate_readonly_sql("WITH spending AS (...) SELECT * FROM spending")

# 拒绝：
""
"DELETE FROM orders"
"INSERT INTO customers (name) VALUES ('Alice')"
"UPDATE products SET list_price = 0"
"DROP TABLE customers"
"PRAGMA table_info(customers)"
"ATTACH DATABASE 'other.db' AS other"
"BEGIN; SELECT * FROM customers"
"SELECT 1; DELETE FROM orders"

# 字符串字面量或注释中的 delete/drop 不可误判：
"SELECT 'delete from orders' AS example -- DROP TABLE customers\nFROM customers"
```

完整 pytest 参数化测试见英文原版“Task 2 / Step 1”。

- [ ] **步骤 2：运行并确认失败**

```bash
python -m pytest tests/test_sql_guard.py -v
```

预期：因 `app.services.sql_guard` 尚不存在而失败。

- [ ] **步骤 3：实现词法扫描和安全校验**

在 `app/services/sql_guard.py`：

1. 定义 `SQLValidationError`。
2. 定义禁止关键字集合：`ALTER`、`ANALYZE`、`ATTACH`、`BEGIN`、`COMMIT`、`CREATE`、`DELETE`、`DETACH`、`DROP`、`INSERT`、`LOAD_EXTENSION`、`PRAGMA`、`REINDEX`、`RELEASE`、`REPLACE`、`ROLLBACK`、`SAVEPOINT`、`UPDATE`、`VACUUM`。
3. 通过 `_code_tokens(sql)` 扫描 SQL，跳过单引号字符串、双引号/反引号/方括号标识符、行注释和块注释。
4. 通过 `_contains_statement_separator(sql)` 检查字符串和注释外的分号，确保只有一条语句。
5. `validate_readonly_sql`：移除至多一个末尾分号，拒绝空 SQL、多语句、不是 `SELECT`/`WITH` 开头的语句、禁止关键字；若以 `WITH` 开头，必须出现 `SELECT`。

完整实现见英文原版“Task 2 / Step 3”。

- [ ] **步骤 4：运行并确认通过**

```bash
python -m pytest tests/test_sql_guard.py -v
```

预期：`13 passed`。

- [ ] **步骤 5：提交**

```bash
git add app/services tests/test_sql_guard.py
git commit -m "feat: guard readonly sql statements"
```

## 任务 3：实现 Schema 读取和受 SQLite authorizer 保护的查询执行

**文件：**
- 创建：`app/services/schema_reader.py`
- 创建：`app/services/query_executor.py`
- 创建：`tests/conftest.py`
- 创建：`tests/test_query_executor.py`

**接口：**
- 消费：`create_demo_database` 和 `validate_readonly_sql`。
- 产出：`get_schema_summary(db_path: Path) -> str`。
- 产出：`QueryResult(columns, rows, row_count, truncated)` 冻结 dataclass。
- 产出：`QueryExecutionError` 和 `execute_readonly_query(db_path, sql, max_rows=200)`。

- [ ] **步骤 1：先写失败的 Schema 和执行器测试**

`tests/conftest.py` 提供 `demo_db_path` fixture：为每个测试在 `tmp_path` 建立新数据库。

`tests/test_query_executor.py` 必须断言：

- `get_schema_summary` 包含 `TABLE customers`、`email TEXT`、`FOREIGN KEY customer_id -> customers.id` 和 `TABLE order_items`。
- `SELECT name, city FROM customers ORDER BY id LIMIT 2` 返回列、两行中文客户、`row_count == 2`、`truncated is False`。
- 插入 10 个客户后，`max_rows=3` 时仅返回 3 行且 `truncated is True`。
- `SELECT missing_column FROM customers` 抛 `QueryExecutionError`，文字包含“查询执行失败”，但不得泄露数据库文件路径。

完整测试见英文原版“Task 3 / Step 1”。

- [ ] **步骤 2：运行并确认失败**

```bash
python -m pytest tests/test_query_executor.py -v
```

预期：因 `query_executor`、`schema_reader` 不存在而失败。

- [ ] **步骤 3：实现 Schema 格式化与受限执行器**

`schema_reader.py`：

- 查询 `sqlite_master` 获得所有非 `sqlite_%` 表。
- 对每张表执行 `PRAGMA table_info` 和 `PRAGMA foreign_key_list`。
- 按如下文本输出，供模型提示词使用：

```text
TABLE customers: id INTEGER, name TEXT, ...
FOREIGN KEY customer_id -> customers.id
```

`query_executor.py`：

- 声明 `QueryExecutionError` 和 `@dataclass(frozen=True) QueryResult`。
- 定义 `DENIED_AUTHORIZER_ACTIONS`，包含所有 create/drop/alter、insert/update/delete、attach/detach、pragma、reindex、transaction 等 `sqlite3.SQLITE_*` 动作常量。
- `sqlite3.Connection.set_authorizer` 的回调在受禁止操作时返回 `sqlite3.SQLITE_DENY`，其他情况返回 `sqlite3.SQLITE_OK`。
- 调用 `validate_readonly_sql`。
- 使用 `file:{absolute_path}?mode=ro` URI 和 `sqlite3.connect(uri=True)` 建立只读连接。
- 使用 `fetchmany(max_rows + 1)` 判断是否截断，再只返回最多 `max_rows` 条。
- 将 `sqlite3.DatabaseError` 映射为中文 `QueryExecutionError`，不得拼接文件路径或原始数据库错误。

完整可复制代码见英文原版“Task 3 / Step 3”。

- [ ] **步骤 4：运行全部已有后端测试并确认通过**

```bash
python -m pytest tests/test_seed.py tests/test_sql_guard.py tests/test_query_executor.py -v
```

预期：全部通过。注意：Schema Reader 的独立连接可使用 `PRAGMA`；Query Executor 在连接创建后才安装 authorizer。

- [ ] **步骤 5：提交**

```bash
git add app/services/schema_reader.py app/services/query_executor.py tests/conftest.py tests/test_query_executor.py
git commit -m "feat: add schema reader and readonly query executor"
```

## 任务 4：实现 OpenAI 兼容 SQL 生成和 FastAPI 接口

**文件：**
- 创建：`app/api/__init__.py`
- 创建：`app/api/schemas.py`
- 创建：`app/api/routes.py`
- 创建：`app/services/llm_client.py`
- 创建：`app/main.py`
- 创建：`tests/test_api.py`

**接口：**
- 消费：`get_schema_summary`、`validate_readonly_sql`、`execute_readonly_query`。
- 产出：`ProviderConfig`、`GenerateSQLRequest`、`ExecuteSQLRequest`、`GenerateSQLResponse`、`ExecuteSQLResponse`。
- 产出：`generate_sql(provider, question, schema_summary) -> str`。
- 产出：`create_app(db_path: Path | None = None) -> FastAPI`。
- 产出：`POST /api/generate-sql`、`POST /api/execute-sql`。

- [ ] **步骤 1：写使用假 LLM 的失败接口测试**

`tests/test_api.py` 要构造临时数据库和 TestClient，并将：

```python
app.state.llm_generate = lambda provider, question, schema: "SELECT name, city FROM customers ORDER BY id"
```

写入应用状态，从而确保测试不会访问真实外部 API。测试覆盖：

1. `/api/generate-sql` 接收 schema、能去掉模型输出的 ```sql 代码块、返回“SQL 已生成，请确认后执行。”。
2. 假模型返回 `DELETE FROM orders` 时，生成接口返回 HTTP 422，`detail` 中含“只读”。
3. `/api/execute-sql` 正常返回列、行、行数与截断标志。
4. `/api/execute-sql` 拒绝 `DELETE FROM orders` 并返回 HTTP 422。

完整测试见英文原版“Task 4 / Step 1”。

- [ ] **步骤 2：运行并确认失败**

```bash
python -m pytest tests/test_api.py -v
```

预期：因 `app.main` 不存在而失败。

- [ ] **步骤 3：定义 Pydantic 模型**

在 `app/api/schemas.py` 定义：

```python
class ProviderConfig(BaseModel):
    base_url: str
    api_key: str
    model: str

class GenerateSQLRequest(BaseModel):
    question: str
    provider: ProviderConfig

class ExecuteSQLRequest(BaseModel):
    sql: str

class GenerateSQLResponse(BaseModel):
    sql: str
    schema_summary: str
    message: str

class ExecuteSQLResponse(BaseModel):
    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool
```

使用 `Field` 设置以下长度限制：Base URL 1–500、API Key 1–1000、模型 1–200、问题 1–2000、SQL 1–10000。完整代码见英文原版“Task 4 / Step 3”。

- [ ] **步骤 4：实现 OpenAI Chat Completions 兼容调用**

`app/services/llm_client.py` 必须：

- 定义 `LLMServiceError`。
- 使用 `base_url.rstrip('/') + '/chat/completions'` 形成目标地址。
- 用 HTTPX `POST` 请求发送：

```python
{
  "model": provider.model,
  "temperature": 0,
  "messages": [
    {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(schema_summary=schema_summary)},
    {"role": "user", "content": question}
  ]
}
```

- 请求头只包含临时构造的 `Authorization: Bearer {provider.api_key}`。
- 用 30 秒 timeout。
- 从 `choices[0].message.content` 读取字符串。
- 用正则兼容去除完整的 ```sql ... ``` 或 ``` ... ``` 包装。
- 对 HTTP、JSON、响应字段等任何失败返回同一不泄密错误：“模型服务调用失败，请检查 Base URL、API Key、模型名称和网络连接。”

完整实现见英文原版“Task 4 / Step 4”。

- [ ] **步骤 5：实现路由与应用工厂**

`app/api/routes.py`：

- `POST /api/generate-sql`：读取 `request.app.state.db_path`，调用 Schema Reader；再调用 `request.app.state.llm_generate`；最后必须调用 `validate_readonly_sql`。模型服务错误映射 502；模型 SQL 未通过校验映射 422。
- `POST /api/execute-sql`：调用 `execute_readonly_query`；SQL Guard 错误和执行错误均映射为 422。

`app/main.py`：

- `PROJECT_ROOT` 指向项目根目录；默认数据库是 `data/demo.db`；静态目录是 `app/static`。
- `create_app` 先调用 `create_demo_database`，再创建 `FastAPI(title="SQLbot")`。
- 在 `app.state` 上赋值 `db_path` 和可替换的 `llm_generate`。
- 注册路由，最后 `app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")`。
- 文件末尾保留 `app = create_app()`，供 Uvicorn 使用。

完整代码见英文原版“Task 4 / Step 5”。

- [ ] **步骤 6：运行全部后端测试**

```bash
python -m pytest tests/test_seed.py tests/test_sql_guard.py tests/test_query_executor.py tests/test_api.py -v
```

预期：全部通过；确认每个生成接口测试都通过 `app.state.llm_generate` 注入 fake，因此没有外网请求。

- [ ] **步骤 7：提交**

```bash
git add app/api app/main.py app/services/llm_client.py tests/test_api.py
git commit -m "feat: add sql generation and execution api"
```

## 任务 5：构建带本地 Provider 设置和显式执行确认的网页

**文件：**
- 创建：`app/static/index.html`
- 创建：`app/static/styles.css`
- 创建：`app/static/app.js`

**接口：**
- 消费：`POST /api/generate-sql`（`{question, provider}`）和 `POST /api/execute-sql`（`{sql}`）。
- 产出：localStorage 键 `sqlbot.providerSettings`，保存 `{baseUrl, apiKey, model}`。

- [ ] **步骤 1：创建页面结构与可访问控件**

`index.html` 必须具备以下 ID：

```text
settings-form, base-url, model, api-key, clear-settings, toggle-settings,
settings-message, question-form, question, generate-button, sql, copy-sql,
execute-button, feedback, results, result-meta, result-table
```

页面包括：顶部产品标题；可折叠模型设置表单；问题输入表单；可编辑 SQL 文本框；复制和执行按钮；实时反馈区；结果表格区。

API Key 使用 `type="password"`，执行按钮初始 `disabled`，结果区域初始 `hidden`。完整 HTML 见英文原版“Task 5 / Step 1”。

- [ ] **步骤 2：实现前端状态、API 请求和结果渲染**

`app.js` 必须：

1. 定义 `STORAGE_KEY = "sqlbot.providerSettings"`。
2. `loadSettings()` 从 localStorage 恢复配置；JSON 解析失败时删除坏数据。
3. 保存时写 `{ baseUrl, apiKey, model }`；清除时删除 localStorage，并清空 Key 和模型。
4. `requestJson` 使用 `fetch`，非 2xx 时抛出 API 返回的 `detail`。
5. 生成请求传 `{ question, provider: { base_url, api_key, model } }`。
6. 生成成功后只写入 SQL 文本框并启用执行按钮，**不得自动调用执行接口**。
7. 执行请求只传 `{ sql }`。
8. `renderResults` 使用 DOM API 创建 `thead`、`tbody`；值为 `null` 时显示 `NULL`，不得通过字符串拼接插入用户/模型内容。
9. 在加载、成功和失败时显示可见反馈；错误不能清空问题、设置或 SQL。
10. 复制 SQL 使用 `navigator.clipboard.writeText`。

完整 JavaScript 见英文原版“Task 5 / Step 2”。

- [ ] **步骤 3：实现响应式样式**

`styles.css` 要求：

- 浅色、简洁的单页布局；宽度限制在 980px。
- 明确的卡片边界、聚焦状态、成功/错误反馈颜色和可横向滚动的表格。
- SQL 文本框使用等宽字体。
- 小于 640px 时设置表单从两列改为一列。

完整 CSS 见英文原版“Task 5 / Step 3”。

- [ ] **步骤 4：启动并手动验证网页流程**

```bash
python -m uvicorn app.main:app --reload
```

预期：监听 `http://127.0.0.1:8000`。

在浏览器检查：

1. 页面可加载。
2. 保存样例设置、刷新后仍存在。
3. 清除设置、刷新后 Key 和模型为空。
4. 未填写完整设置时生成，显示错误且不清空问题。
5. 手动输入 `SELECT name FROM customers` 后执行，表格正确显示。
6. 输入 `DELETE FROM orders` 后执行，显示安全错误，数据库不变。

检查后用 `Ctrl+C` 停止 Uvicorn。

- [ ] **步骤 5：提交**

```bash
git add app/static
git commit -m "feat: add sqlbot browser interface"
```

## 任务 6：补全文档并完成全量验证

**文件：**
- 创建：`README.md`
- 修改：`tests/test_api.py`

**接口：**
- 消费：任务 1–5 的完整应用与测试套件。
- 产出：可重复执行的安装、启动、配置、测试和安全边界文档。

- [ ] **步骤 1：先增加静态首页 smoke test**

在 `tests/test_api.py` 追加：

```python
def test_root_serves_sqlbot_page(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/")

    assert response.status_code == 200
    assert "<title>SQLbot</title>" in response.text
    assert 'id="generate-button"' in response.text
```

- [ ] **步骤 2：运行 smoke test**

```bash
python -m pytest tests/test_api.py::test_root_serves_sqlbot_page -v
```

预期：`1 passed`。

- [ ] **步骤 3：编写 README**

`README.md` 需用中文说明：

- 产品目标：自然语言 → SQL 预览 → 用户确认 → SQLite 查询。
- 内置表、OpenAI Chat Completions 兼容性、localStorage、显式执行、200 行限制。
- Python 3.11+ 前置条件。
- 虚拟环境与 `pip install -r requirements.txt` 安装命令。
- `python -m uvicorn app.main:app --reload` 启动命令和 `http://127.0.0.1:8000` 地址。
- `data/demo.db` 首次启动自动创建，删除后可重新生成。
- Base URL、API Key、模型名称的使用步骤。
- localStorage 仅适用于本机开发、可点击“清除配置”。
- 只允许 `SELECT`/`WITH ... SELECT`、拒绝写操作/DDL/PRAGMA/ATTACH/事务/多语句；不应接入真实生产数据库。
- `python -m pytest -v` 测试命令，且测试无需 API Key。

完整 README 文本见英文原版“Task 6 / Step 3”。

- [ ] **步骤 4：运行全量测试**

```bash
python -m pytest -v
```

预期：所有测试通过，覆盖种子数据、SQL Guard、只读执行、API、静态页面。

- [ ] **步骤 5：对运行中的服务执行最终安全验证**

先启动：

```bash
python -m uvicorn app.main:app --port 8000
```

再在另一终端执行：

```bash
curl -s -X POST http://127.0.0.1:8000/api/execute-sql \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT COUNT(*) AS order_count FROM orders"}'

curl -s -X POST http://127.0.0.1:8000/api/execute-sql \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT 1; DELETE FROM orders"}'
```

预期：第一个命令返回 HTTP 200，包含 `columns`、`rows`、`row_count`、`truncated`；第二个命令返回 HTTP 422，`detail` 说明只读 SQL 限制。完成后停止 Uvicorn。

- [ ] **步骤 6：提交文档和最终测试**

```bash
git add README.md tests/test_api.py
git commit -m "docs: add sqlbot setup and safety guide"
git status --short
```

预期：README 与 smoke test 已提交，`git status --short` 无输出。

## 规格覆盖检查

| 规格要求 | 对应任务 |
| --- | --- |
| OpenAI 兼容 SQL 生成 | 任务 4 |
| FastAPI 同源 API 和网页 | 任务 4、5 |
| SQLite 示例 Schema 和种子数据 | 任务 1 |
| 动态 Schema 提示词 | 任务 3、4 |
| 可编辑、用户确认后执行 | 任务 5 |
| SELECT/CTE 限制、禁止写操作/DDL/多语句 | 任务 2–4 |
| SQLite 只读 authorizer、返回行限制 | 任务 3 |
| localStorage 设置及无服务端密钥持久化 | 任务 5、6 |
| 不重试、不伪造结果、清晰错误 | 任务 4、5 |
| 无真实密钥的自动化测试 | 任务 1–4、6 |

## 计划自检

- 本 MVP 是单一可运行子项目，无需拆为多个实现计划。
- 所有后续任务使用的接口均由前置任务明确定义。
- 任务中没有未定义的待办项、延后实现项或未说明的测试步骤。
- 所有确认过的设计规格都已映射到至少一个实现任务。
