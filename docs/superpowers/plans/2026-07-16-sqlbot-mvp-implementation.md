# SQLbot MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI web application that translates natural-language questions into user-confirmed, read-only SQLite queries through an OpenAI Chat Completions-compatible API.

**Architecture:** A single FastAPI process serves the static single-page UI and two JSON endpoints. The LLM adapter only returns SQL text; all SQL—whether model-generated or edited by a user—passes through a shared read-only guard and executes through a SQLite authorizer-backed query executor against a seeded demo database.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, HTTPX, SQLite (`sqlite3`), pytest, Starlette TestClient, HTML/CSS/vanilla JavaScript.

## Global Constraints

- Support OpenAI **Chat Completions-compatible** endpoints only; do not add an Anthropic-specific provider in this MVP.
- Keep API Base URL, API Key, and model name in browser `localStorage`; never write API keys to server logs, responses, SQLite, source files, or `.env` files.
- Serve the UI and API from the same FastAPI origin; do not add CORS middleware.
- Use only `data/demo.db`, seeded with `customers`, `products`, `orders`, and `order_items`.
- Generate SQL but never execute it automatically from the generation endpoint.
- Allow one read-only SQLite `SELECT` or `WITH ... SELECT` statement only; reject writes, DDL, SQLite administration commands, transaction control, and multiple statements.
- Enforce the read-only restriction both before execution and at SQLite execution time.
- Return at most 200 rows; expose whether the result was truncated.
- Do not depend on a real API key or external model server in automated tests.
- Keep modules focused: database seeding, SQL validation, schema reading, execution, LLM transport, HTTP routes, and UI must remain separate.

---

## Planned File Structure

```text
app/
├── __init__.py                    # Python package marker
├── main.py                         # App factory, startup seeding, static-file mounting
├── api/
│   ├── __init__.py
│   ├── routes.py                   # POST /api/generate-sql and POST /api/execute-sql
│   └── schemas.py                  # HTTP request/response Pydantic models
├── database/
│   ├── __init__.py
│   └── seed.py                     # Creates deterministic demo SQLite schema and fixtures
├── services/
│   ├── __init__.py
│   ├── llm_client.py               # OpenAI-compatible Chat Completions transport and prompting
│   ├── query_executor.py            # SQLite read-only authorizer and bounded result conversion
│   ├── schema_reader.py             # Schema introspection and prompt-ready formatting
│   └── sql_guard.py                # SQL normalization and lexical safety validation
└── static/
    ├── app.js                      # Browser state, API calls, rendering, localStorage
    ├── index.html                  # Accessible single-page markup
    └── styles.css                  # Responsive application styles

tests/
├── conftest.py                     # Per-test demo DB and FastAPI app fixtures
├── test_api.py                     # Route-level behavior with a fake LLM generator
├── test_query_executor.py          # Read-only execution, truncation, error mapping
├── test_seed.py                    # Seeded schema and data invariants
└── test_sql_guard.py               # Allowed and blocked SQL validation cases

requirements.txt                    # Runtime and test dependencies
.env.example                        # Non-secret example application settings only
.gitignore                          # Prevents local env, cache, and runtime DB artifacts from tracking
README.md                           # Setup, local run, model configuration, limitations, test commands
```

## Task 1: Bootstrap the Python project and deterministic demo database

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/database/__init__.py`
- Create: `app/database/seed.py`
- Create: `tests/test_seed.py`
- Modify: `docs/superpowers/specs/2026-07-16-sqlbot-mvp-design.md` (no change expected; use only as reference)

**Interfaces:**
- Produces: `create_demo_database(db_path: pathlib.Path) -> None`.
- Produces: a database containing `customers`, `products`, `orders`, and `order_items` with deterministic related rows.
- Consumes: no earlier project interfaces.

- [ ] **Step 1: Initialize source control so the requested incremental commits are possible**

Run:

```bash
git init
git add docs/superpowers/specs/2026-07-16-sqlbot-mvp-design.md
git commit -m "docs: add sqlbot mvp design"
```

Expected: a new repository exists and the confirmed design document is committed. If Git lacks `user.name` or `user.email`, configure them locally for this repository before retrying the commit.

- [ ] **Step 2: Add project dependencies and local-file exclusions**

Create `requirements.txt`:

```text
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30,<1.0
httpx>=0.27,<1.0
pytest>=8.0,<9.0
```

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
.env
data/demo.db
```

Create `.env.example`:

```dotenv
# This MVP receives model credentials from the browser settings panel.
# Do not put OPENAI_API_KEY in this file.
HOST=127.0.0.1
PORT=8000
```

- [ ] **Step 3: Write the failing database-seeding tests**

Create `tests/test_seed.py`:

```python
import sqlite3
from pathlib import Path

from app.database.seed import create_demo_database


def test_seed_creates_expected_tables_and_related_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "demo.db"

    create_demo_database(db_path)

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        order_count = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        item_count = connection.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
        joined_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM orders AS o
            JOIN customers AS c ON c.id = o.customer_id
            JOIN order_items AS oi ON oi.order_id = o.id
            JOIN products AS p ON p.id = oi.product_id
            """
        ).fetchone()[0]

    assert {"customers", "products", "orders", "order_items"} <= table_names
    assert order_count >= 6
    assert item_count >= 8
    assert joined_count == item_count


def test_seed_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "demo.db"

    create_demo_database(db_path)
    create_demo_database(db_path)

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 5
```

- [ ] **Step 4: Run the seed tests to verify they fail**

Run:

```bash
python -m pytest tests/test_seed.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.database.seed'`.

- [ ] **Step 5: Implement the seed function and package markers**

Create empty files `app/__init__.py` and `app/database/__init__.py`.

Create `app/database/seed.py`:

```python
from pathlib import Path
import sqlite3


SCHEMA_SQL = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    list_price REAL NOT NULL CHECK (list_price >= 0)
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'pending', 'cancelled')),
    total_amount REAL NOT NULL CHECK (total_amount >= 0)
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0)
);
"""


def create_demo_database(db_path: Path) -> None:
    """Create a small, deterministic e-commerce SQLite database once."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'customers'"
        ).fetchone()
        if exists:
            return

        connection.executescript(SCHEMA_SQL)
        connection.executemany(
            "INSERT INTO customers (id, name, email, city, created_at) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "张三", "zhangsan@example.com", "上海", "2024-01-10"),
                (2, "李四", "lisi@example.com", "北京", "2024-02-15"),
                (3, "王五", "wangwu@example.com", "深圳", "2024-03-05"),
                (4, "赵六", "zhaoliu@example.com", "杭州", "2024-04-22"),
                (5, "陈七", "chenqi@example.com", "成都", "2024-05-18"),
            ],
        )
        connection.executemany(
            "INSERT INTO products (id, name, category, list_price) VALUES (?, ?, ?, ?)",
            [
                (1, "机械键盘", "电脑配件", 399.0),
                (2, "无线鼠标", "电脑配件", 159.0),
                (3, "降噪耳机", "音频设备", 799.0),
                (4, "显示器支架", "办公用品", 249.0),
                (5, "笔记本电脑包", "办公用品", 189.0),
            ],
        )
        connection.executemany(
            "INSERT INTO orders (id, customer_id, order_date, status, total_amount) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, "2024-06-01", "completed", 558.0),
                (2, 2, "2024-06-03", "completed", 799.0),
                (3, 1, "2024-07-10", "completed", 648.0),
                (4, 3, "2024-07-12", "pending", 249.0),
                (5, 4, "2024-08-01", "cancelled", 189.0),
                (6, 2, "2024-08-08", "completed", 957.0),
            ],
        )
        connection.executemany(
            "INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, 1, 1, 399.0),
                (2, 1, 2, 1, 159.0),
                (3, 2, 3, 1, 799.0),
                (4, 3, 1, 1, 399.0),
                (5, 3, 5, 1, 189.0),
                (6, 3, 2, 1, 60.0),
                (7, 4, 4, 1, 249.0),
                (8, 5, 5, 1, 189.0),
                (9, 6, 3, 1, 799.0),
                (10, 6, 2, 1, 158.0),
            ],
        )
```

- [ ] **Step 6: Run the seed tests to verify they pass**

Run:

```bash
python -m pytest tests/test_seed.py -v
```

Expected: `2 passed`.

- [ ] **Step 7: Commit the bootstrap and demo database**

Run:

```bash
git add requirements.txt .gitignore .env.example app tests/test_seed.py
git commit -m "feat: add seeded sqlite demo database"
```

Expected: one commit containing project bootstrap and database seed functionality.

## Task 2: Implement the read-only SQL guard with test-first coverage

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/sql_guard.py`
- Create: `tests/test_sql_guard.py`

**Interfaces:**
- Produces: `class SQLValidationError(ValueError)`.
- Produces: `validate_readonly_sql(sql: str) -> str`, which returns a stripped single query without a terminal semicolon or raises `SQLValidationError`.
- Consumes: no project interface other than Python standard library.

- [ ] **Step 1: Write the failing SQL guard tests**

Create `tests/test_sql_guard.py`:

```python
import pytest

from app.services.sql_guard import SQLValidationError, validate_readonly_sql


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT id, name FROM customers;", "SELECT id, name FROM customers"),
        (
            "WITH spending AS (SELECT customer_id, SUM(total_amount) AS total FROM orders GROUP BY customer_id) SELECT * FROM spending",
            "WITH spending AS (SELECT customer_id, SUM(total_amount) AS total FROM orders GROUP BY customer_id) SELECT * FROM spending",
        ),
    ],
)
def test_allows_one_readonly_select_statement(sql: str, expected: str) -> None:
    assert validate_readonly_sql(sql) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "DELETE FROM orders",
        "INSERT INTO customers (name) VALUES ('Alice')",
        "UPDATE products SET list_price = 0",
        "DROP TABLE customers",
        "PRAGMA table_info(customers)",
        "ATTACH DATABASE 'other.db' AS other",
        "BEGIN; SELECT * FROM customers",
        "SELECT 1; DELETE FROM orders",
    ],
)
def test_rejects_non_readonly_or_multiple_statements(sql: str) -> None:
    with pytest.raises(SQLValidationError):
        validate_readonly_sql(sql)


def test_ignores_sql_comment_and_string_keyword_text() -> None:
    sql = "SELECT 'delete from orders' AS example -- DROP TABLE customers\nFROM customers"

    assert validate_readonly_sql(sql) == sql
```

- [ ] **Step 2: Run the SQL guard tests to verify they fail**

Run:

```bash
python -m pytest tests/test_sql_guard.py -v
```

Expected: collection fails because `app.services.sql_guard` does not exist.

- [ ] **Step 3: Implement statement scanning and allow-list validation**

Create an empty `app/services/__init__.py`.

Create `app/services/sql_guard.py`:

```python
from __future__ import annotations

import re


class SQLValidationError(ValueError):
    """Raised when SQL is not exactly one permitted read-only query."""


FORBIDDEN_KEYWORDS = {
    "ALTER",
    "ANALYZE",
    "ATTACH",
    "BEGIN",
    "COMMIT",
    "CREATE",
    "DELETE",
    "DETACH",
    "DROP",
    "INSERT",
    "LOAD_EXTENSION",
    "PRAGMA",
    "REINDEX",
    "RELEASE",
    "REPLACE",
    "ROLLBACK",
    "SAVEPOINT",
    "UPDATE",
    "VACUUM",
}


def _code_tokens(sql: str) -> list[str]:
    """Return upper-case word tokens excluding quoted strings and comments."""
    tokens: list[str] = []
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < length else ""

        if char == "'":
            index += 1
            while index < length:
                if sql[index] == "'" and index + 1 < length and sql[index + 1] == "'":
                    index += 2
                elif sql[index] == "'":
                    index += 1
                    break
                else:
                    index += 1
            continue
        if char in ('\"', '`'):
            quote = char
            index += 1
            while index < length and sql[index] != quote:
                index += 1
            index += 1
            continue
        if char == "[":
            closing = sql.find("]", index + 1)
            index = length if closing == -1 else closing + 1
            continue
        if char == "-" and next_char == "-":
            newline = sql.find("\n", index + 2)
            index = length if newline == -1 else newline + 1
            continue
        if char == "/" and next_char == "*":
            closing = sql.find("*/", index + 2)
            index = length if closing == -1 else closing + 2
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < length and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            tokens.append(sql[index:end].upper())
            index = end
            continue
        index += 1

    return tokens


def _contains_statement_separator(sql: str) -> bool:
    """Detect a semicolon outside comments and quoted identifiers/literals."""
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < length else ""
        if char == "'":
            index += 1
            while index < length:
                if sql[index] == "'" and index + 1 < length and sql[index + 1] == "'":
                    index += 2
                elif sql[index] == "'":
                    index += 1
                    break
                else:
                    index += 1
            continue
        if char in ('\"', '`'):
            closing = sql.find(char, index + 1)
            index = length if closing == -1 else closing + 1
            continue
        if char == "[":
            closing = sql.find("]", index + 1)
            index = length if closing == -1 else closing + 1
            continue
        if char == "-" and next_char == "-":
            newline = sql.find("\n", index + 2)
            index = length if newline == -1 else newline + 1
            continue
        if char == "/" and next_char == "*":
            closing = sql.find("*/", index + 2)
            index = length if closing == -1 else closing + 2
            continue
        if char == ";":
            return True
        index += 1
    return False


def validate_readonly_sql(sql: str) -> str:
    normalized = sql.strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    if not normalized:
        raise SQLValidationError("请输入一条非空的只读 SQL 查询。")
    if _contains_statement_separator(normalized):
        raise SQLValidationError("只允许执行一条 SQL 查询。")

    tokens = _code_tokens(normalized)
    if not tokens or tokens[0] not in {"SELECT", "WITH"}:
        raise SQLValidationError("只允许 SELECT 或 WITH ... SELECT 查询。")

    forbidden = sorted(set(tokens) & FORBIDDEN_KEYWORDS)
    if forbidden:
        raise SQLValidationError(f"不允许使用 SQL 关键字：{', '.join(forbidden)}。")

    if tokens[0] == "WITH" and "SELECT" not in tokens:
        raise SQLValidationError("WITH 查询必须最终返回 SELECT 结果。")

    return normalized
```

- [ ] **Step 4: Run the SQL guard tests to verify they pass**

Run:

```bash
python -m pytest tests/test_sql_guard.py -v
```

Expected: `13 passed`.

- [ ] **Step 5: Commit the SQL guard**

Run:

```bash
git add app/services tests/test_sql_guard.py
git commit -m "feat: guard readonly sql statements"
```

Expected: one commit implementing and testing SQL lexical validation.

## Task 3: Add schema introspection and SQLite-authorized query execution

**Files:**
- Create: `app/services/schema_reader.py`
- Create: `app/services/query_executor.py`
- Create: `tests/test_query_executor.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: `create_demo_database(db_path: Path) -> None` and `validate_readonly_sql(sql: str) -> str`.
- Produces: `get_schema_summary(db_path: Path) -> str`.
- Produces: `@dataclass(frozen=True) QueryResult(columns: list[str], rows: list[list[object]], row_count: int, truncated: bool)`.
- Produces: `class QueryExecutionError(RuntimeError)` and `execute_readonly_query(db_path: Path, sql: str, max_rows: int = 200) -> QueryResult`.

- [ ] **Step 1: Write the failing executor and schema tests**

Create `tests/conftest.py`:

```python
from pathlib import Path

import pytest

from app.database.seed import create_demo_database


@pytest.fixture
def demo_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "demo.db"
    create_demo_database(db_path)
    return db_path
```

Create `tests/test_query_executor.py`:

```python
import sqlite3

import pytest

from app.services.query_executor import QueryExecutionError, execute_readonly_query
from app.services.schema_reader import get_schema_summary


def test_schema_summary_contains_tables_columns_and_relationships(demo_db_path) -> None:
    summary = get_schema_summary(demo_db_path)

    assert "TABLE customers" in summary
    assert "email TEXT" in summary
    assert "FOREIGN KEY customer_id -> customers.id" in summary
    assert "TABLE order_items" in summary


def test_executor_returns_columns_rows_and_result_count(demo_db_path) -> None:
    result = execute_readonly_query(
        demo_db_path,
        "SELECT name, city FROM customers ORDER BY id LIMIT 2",
    )

    assert result.columns == ["name", "city"]
    assert result.rows == [["张三", "上海"], ["李四", "北京"]]
    assert result.row_count == 2
    assert result.truncated is False


def test_executor_truncates_at_requested_max_rows(demo_db_path) -> None:
    with sqlite3.connect(demo_db_path) as connection:
        connection.executemany(
            "INSERT INTO customers (name, email, city, created_at) VALUES (?, ?, ?, ?)",
            [(f"客户{i}", f"customer{i}@example.com", "上海", "2024-01-01") for i in range(10)],
        )

    result = execute_readonly_query(
        demo_db_path,
        "SELECT id FROM customers ORDER BY id",
        max_rows=3,
    )

    assert result.row_count == 3
    assert len(result.rows) == 3
    assert result.truncated is True


def test_executor_maps_sqlite_failures_without_database_path(demo_db_path) -> None:
    with pytest.raises(QueryExecutionError) as error:
        execute_readonly_query(demo_db_path, "SELECT missing_column FROM customers")

    assert "查询执行失败" in str(error.value)
    assert str(demo_db_path) not in str(error.value)
```

- [ ] **Step 2: Run the executor tests to verify they fail**

Run:

```bash
python -m pytest tests/test_query_executor.py -v
```

Expected: collection fails because `query_executor` and `schema_reader` do not exist.

- [ ] **Step 3: Implement schema formatting and bounded, authorized execution**

Create `app/services/schema_reader.py`:

```python
from pathlib import Path
import sqlite3


def get_schema_summary(db_path: Path) -> str:
    """Return prompt-ready table, column, and foreign-key metadata."""
    lines: list[str] = []
    with sqlite3.connect(db_path) as connection:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        for (table_name,) in table_rows:
            columns = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            foreign_keys = connection.execute(f'PRAGMA foreign_key_list("{table_name}")').fetchall()
            column_text = ", ".join(f"{column[1]} {column[2]}" for column in columns)
            lines.append(f"TABLE {table_name}: {column_text}")
            for foreign_key in foreign_keys:
                lines.append(
                    f"FOREIGN KEY {foreign_key[3]} -> {foreign_key[2]}.{foreign_key[4]}"
                )
    return "\n".join(lines)
```

Create `app/services/query_executor.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from app.services.sql_guard import SQLValidationError, validate_readonly_sql


class QueryExecutionError(RuntimeError):
    """Raised when a permitted query cannot execute safely."""


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool


DENIED_AUTHORIZER_ACTIONS = {
    sqlite3.SQLITE_ALTER_TABLE,
    sqlite3.SQLITE_ANALYZE,
    sqlite3.SQLITE_ATTACH,
    sqlite3.SQLITE_CREATE_INDEX,
    sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_INDEX,
    sqlite3.SQLITE_CREATE_TEMP_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
    sqlite3.SQLITE_CREATE_TEMP_VIEW,
    sqlite3.SQLITE_CREATE_TRIGGER,
    sqlite3.SQLITE_CREATE_VIEW,
    sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_DETACH,
    sqlite3.SQLITE_DROP_INDEX,
    sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_DROP_TEMP_INDEX,
    sqlite3.SQLITE_DROP_TEMP_TABLE,
    sqlite3.SQLITE_DROP_TEMP_TRIGGER,
    sqlite3.SQLITE_DROP_TEMP_VIEW,
    sqlite3.SQLITE_DROP_TRIGGER,
    sqlite3.SQLITE_DROP_VIEW,
    sqlite3.SQLITE_INSERT,
    sqlite3.SQLITE_PRAGMA,
    sqlite3.SQLITE_REINDEX,
    sqlite3.SQLITE_TRANSACTION,
    sqlite3.SQLITE_UPDATE,
}


def _readonly_authorizer(action_code: int, _arg1: str | None, _arg2: str | None, _db: str | None, _trigger: str | None) -> int:
    if action_code in DENIED_AUTHORIZER_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def execute_readonly_query(db_path: Path, sql: str, max_rows: int = 200) -> QueryResult:
    if max_rows < 1:
        raise ValueError("max_rows 必须大于 0。")

    try:
        normalized_sql = validate_readonly_sql(sql)
    except SQLValidationError:
        raise

    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            connection.set_authorizer(_readonly_authorizer)
            cursor = connection.execute(normalized_sql)
            if cursor.description is None:
                raise QueryExecutionError("查询没有返回结果集。")
            fetched_rows = cursor.fetchmany(max_rows + 1)
            columns = [column[0] for column in cursor.description]
    except sqlite3.DatabaseError as error:
        raise QueryExecutionError("查询执行失败，请检查表名、字段名和 SQLite 语法。") from error

    truncated = len(fetched_rows) > max_rows
    visible_rows = fetched_rows[:max_rows]
    return QueryResult(
        columns=columns,
        rows=[list(row) for row in visible_rows],
        row_count=len(visible_rows),
        truncated=truncated,
    )
```

- [ ] **Step 4: Run executor and full existing tests to verify they pass**

Run:

```bash
python -m pytest tests/test_seed.py tests/test_sql_guard.py tests/test_query_executor.py -v
```

Expected: all tests pass. If `PRAGMA` is blocked by the executor, confirm the authorizer is installed only after `get_schema_summary` opens its independent metadata connection.

- [ ] **Step 5: Commit schema inspection and guarded execution**

Run:

```bash
git add app/services/schema_reader.py app/services/query_executor.py tests/conftest.py tests/test_query_executor.py
git commit -m "feat: add schema reader and readonly query executor"
```

Expected: one commit containing the database read path and its tests.

## Task 4: Implement OpenAI-compatible SQL generation and FastAPI endpoints

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/schemas.py`
- Create: `app/api/routes.py`
- Create: `app/services/llm_client.py`
- Create: `app/main.py`
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes: `get_schema_summary(db_path: Path) -> str`, `validate_readonly_sql(sql: str) -> str`, and `execute_readonly_query(db_path: Path, sql: str, max_rows: int = 200) -> QueryResult`.
- Produces: `class ProviderConfig(BaseModel)`, `class GenerateSQLRequest(BaseModel)`, `class ExecuteSQLRequest(BaseModel)`, `class GenerateSQLResponse(BaseModel)`, and `class ExecuteSQLResponse(BaseModel)`.
- Produces: `generate_sql(provider: ProviderConfig, question: str, schema_summary: str) -> str`.
- Produces: `create_app(db_path: Path | None = None) -> FastAPI`.
- Produces: `POST /api/generate-sql` and `POST /api/execute-sql`.

- [ ] **Step 1: Write the failing endpoint tests using a fake LLM generator**

Create `tests/test_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from app.database.seed import create_demo_database
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "demo.db"
    create_demo_database(db_path)
    app = create_app(db_path)
    app.state.llm_generate = lambda provider, question, schema: "SELECT name, city FROM customers ORDER BY id"
    return TestClient(app)


def provider_payload() -> dict[str, str]:
    return {
        "base_url": "https://example.test/v1",
        "api_key": "test-key",
        "model": "test-model",
    }


def test_generate_sql_passes_schema_to_llm_and_returns_unexecuted_sql(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    captured: dict[str, str] = {}

    def fake_generate(provider, question, schema):
        captured["question"] = question
        captured["schema"] = schema
        return "```sql\nSELECT name FROM customers\n```"

    client.app.state.llm_generate = fake_generate
    response = client.post(
        "/api/generate-sql",
        json={"question": "列出所有客户", "provider": provider_payload()},
    )

    assert response.status_code == 200
    assert response.json()["sql"] == "SELECT name FROM customers"
    assert response.json()["message"] == "SQL 已生成，请确认后执行。"
    assert captured["question"] == "列出所有客户"
    assert "TABLE customers" in captured["schema"]


def test_generate_sql_rejects_unsafe_model_output(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.app.state.llm_generate = lambda provider, question, schema: "DELETE FROM orders"

    response = client.post(
        "/api/generate-sql",
        json={"question": "删除订单", "provider": provider_payload()},
    )

    assert response.status_code == 422
    assert "只读" in response.json()["detail"]


def test_execute_sql_returns_tabular_data(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/execute-sql",
        json={"sql": "SELECT name, city FROM customers ORDER BY id LIMIT 2"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "columns": ["name", "city"],
        "rows": [["张三", "上海"], ["李四", "北京"]],
        "row_count": 2,
        "truncated": False,
    }


def test_execute_sql_rejects_writes(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post("/api/execute-sql", json={"sql": "DELETE FROM orders"})

    assert response.status_code == 422
    assert "只读" in response.json()["detail"]
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run:

```bash
python -m pytest tests/test_api.py -v
```

Expected: collection fails because `app.main` does not exist.

- [ ] **Step 3: Define request and response models**

Create an empty `app/api/__init__.py`.

Create `app/api/schemas.py`:

```python
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=200)


class GenerateSQLRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    provider: ProviderConfig


class ExecuteSQLRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10000)


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

- [ ] **Step 4: Implement the OpenAI-compatible transport and SQL extraction**

Create `app/services/llm_client.py`:

```python
from __future__ import annotations

import re

import httpx

from app.api.schemas import ProviderConfig


class LLMServiceError(RuntimeError):
    """Raised when the configured compatible model service cannot generate SQL."""


SYSTEM_PROMPT_TEMPLATE = """你是 SQLite 数据分析助手。根据用户问题生成 SQL。

可用数据库 Schema：
{schema_summary}

严格规则：
1. 只返回一条 SQLite SQL 查询。
2. 只允许 SELECT 或 WITH ... SELECT。
3. 只能使用给定的表和字段。
4. 不要解释，不要 Markdown，不要代码块。
5. 对可能返回很多行的查询使用合理的 LIMIT。
"""


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def extract_sql(model_text: str) -> str:
    stripped = model_text.strip()
    fenced = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    return fenced.group(1).strip() if fenced else stripped


def generate_sql(provider: ProviderConfig, question: str, schema_summary: str) -> str:
    payload = {
        "model": provider.model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(schema_summary=schema_summary)},
            {"role": "user", "content": question},
        ],
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                _chat_completions_url(provider.base_url),
                headers={"Authorization": f"Bearer {provider.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise LLMServiceError("模型服务调用失败，请检查 Base URL、API Key、模型名称和网络连接。") from error

    if not isinstance(content, str) or not content.strip():
        raise LLMServiceError("模型服务没有返回可用的 SQL。")
    return extract_sql(content)
```

- [ ] **Step 5: Implement routes and the app factory**

Create `app/api/routes.py`:

```python
from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import ExecuteSQLRequest, ExecuteSQLResponse, GenerateSQLRequest, GenerateSQLResponse
from app.services.llm_client import LLMServiceError, generate_sql
from app.services.query_executor import QueryExecutionError, execute_readonly_query
from app.services.schema_reader import get_schema_summary
from app.services.sql_guard import SQLValidationError, validate_readonly_sql


router = APIRouter(prefix="/api")


@router.post("/generate-sql", response_model=GenerateSQLResponse)
def generate_sql_route(payload: GenerateSQLRequest, request: Request) -> GenerateSQLResponse:
    db_path = request.app.state.db_path
    schema_summary = get_schema_summary(db_path)
    generator = request.app.state.llm_generate
    try:
        sql = validate_readonly_sql(generator(payload.provider, payload.question, schema_summary))
    except LLMServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except SQLValidationError as error:
        raise HTTPException(status_code=422, detail=f"生成的 SQL 未通过只读安全校验：{error}") from error

    return GenerateSQLResponse(
        sql=sql,
        schema_summary=schema_summary,
        message="SQL 已生成，请确认后执行。",
    )


@router.post("/execute-sql", response_model=ExecuteSQLResponse)
def execute_sql_route(payload: ExecuteSQLRequest, request: Request) -> ExecuteSQLResponse:
    try:
        result = execute_readonly_query(request.app.state.db_path, payload.sql)
    except SQLValidationError as error:
        raise HTTPException(status_code=422, detail=f"SQL 未通过只读安全校验：{error}") from error
    except QueryExecutionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return ExecuteSQLResponse(
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
    )
```

Create `app/main.py`:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.database.seed import create_demo_database
from app.services.llm_client import generate_sql


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "demo.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(db_path: Path | None = None) -> FastAPI:
    database_path = db_path or DEFAULT_DB_PATH
    create_demo_database(database_path)

    app = FastAPI(title="SQLbot")
    app.state.db_path = database_path
    app.state.llm_generate = generate_sql
    app.include_router(router)
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
```

- [ ] **Step 6: Run endpoint and full backend tests to verify they pass**

Run:

```bash
python -m pytest tests/test_seed.py tests/test_sql_guard.py tests/test_query_executor.py tests/test_api.py -v
```

Expected: all tests pass. Confirm no test contacts an external HTTP service because every generation test assigns `app.state.llm_generate`.

- [ ] **Step 7: Commit the API and model-generation path**

Run:

```bash
git add app/api app/main.py app/services/llm_client.py tests/test_api.py
git commit -m "feat: add sql generation and execution api"
```

Expected: one commit containing API models, mockable model invocation, and protected endpoints.

## Task 5: Build the browser UI with local-only provider settings and explicit execution

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/styles.css`
- Create: `app/static/app.js`

**Interfaces:**
- Consumes: `POST /api/generate-sql` with `{question, provider}` and `POST /api/execute-sql` with `{sql}`.
- Produces: localStorage key `sqlbot.providerSettings` containing `{baseUrl, apiKey, model}`.
- Produces: UI states for settings, generating, editable SQL, executing, table results, empty result, truncation, and errors.

- [ ] **Step 1: Create the static page shell and required accessible controls**

Create `app/static/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SQLbot</title>
    <link rel="stylesheet" href="/styles.css" />
  </head>
  <body>
    <main class="app-shell">
      <header class="hero">
        <p class="eyebrow">SQLite · Natural Language Query</p>
        <h1>SQLbot</h1>
        <p>用自然语言生成 SQL，确认后再执行。</p>
      </header>

      <section class="panel" aria-labelledby="settings-title">
        <div class="section-heading">
          <h2 id="settings-title">模型设置</h2>
          <button id="toggle-settings" class="text-button" type="button" aria-expanded="true">收起</button>
        </div>
        <form id="settings-form" class="settings-grid">
          <label>API Base URL<input id="base-url" name="baseUrl" type="url" value="https://api.openai.com/v1" required /></label>
          <label>模型名称<input id="model" name="model" type="text" placeholder="gpt-4.1-mini" required /></label>
          <label class="wide">API Key<input id="api-key" name="apiKey" type="password" autocomplete="off" required /></label>
          <div class="actions wide">
            <button type="submit">保存设置</button>
            <button id="clear-settings" class="secondary" type="button">清除配置</button>
          </div>
          <p id="settings-message" class="hint wide" aria-live="polite">仅适合本机开发；不要在多人电脑或生产环境保存真实 API Key。</p>
        </form>
      </section>

      <section class="panel" aria-labelledby="question-title">
        <h2 id="question-title">提问</h2>
        <form id="question-form">
          <label for="question">自然语言问题</label>
          <textarea id="question" rows="4" placeholder="例如：查询销售额最高的 5 个商品" required></textarea>
          <div class="actions"><button id="generate-button" type="submit">生成 SQL</button></div>
        </form>
      </section>

      <section class="panel" aria-labelledby="sql-title">
        <div class="section-heading"><h2 id="sql-title">SQL 预览</h2><button id="copy-sql" class="text-button" type="button">复制 SQL</button></div>
        <textarea id="sql" rows="8" spellcheck="false" placeholder="生成后的 SQL 会显示在这里；你可以在执行前手动编辑。"></textarea>
        <div class="actions"><button id="execute-button" type="button" disabled>执行查询</button></div>
      </section>

      <section id="feedback" class="feedback" aria-live="polite" hidden></section>
      <section id="results" class="panel" aria-labelledby="results-title" hidden>
        <h2 id="results-title">查询结果</h2>
        <p id="result-meta" class="hint"></p>
        <div class="table-wrap"><table id="result-table"></table></div>
      </section>
    </main>
    <script src="/app.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Implement the browser state and API interaction**

Create `app/static/app.js`:

```javascript
const STORAGE_KEY = "sqlbot.providerSettings";
const elements = {
  settingsForm: document.querySelector("#settings-form"),
  baseUrl: document.querySelector("#base-url"),
  model: document.querySelector("#model"),
  apiKey: document.querySelector("#api-key"),
  clearSettings: document.querySelector("#clear-settings"),
  toggleSettings: document.querySelector("#toggle-settings"),
  settingsMessage: document.querySelector("#settings-message"),
  questionForm: document.querySelector("#question-form"),
  question: document.querySelector("#question"),
  generateButton: document.querySelector("#generate-button"),
  sql: document.querySelector("#sql"),
  copySql: document.querySelector("#copy-sql"),
  executeButton: document.querySelector("#execute-button"),
  feedback: document.querySelector("#feedback"),
  results: document.querySelector("#results"),
  resultMeta: document.querySelector("#result-meta"),
  resultTable: document.querySelector("#result-table"),
};

function showFeedback(message, type = "info") {
  elements.feedback.hidden = false;
  elements.feedback.className = `feedback ${type}`;
  elements.feedback.textContent = message;
}

function clearFeedback() {
  elements.feedback.hidden = true;
  elements.feedback.textContent = "";
}

function providerFromForm() {
  return {
    base_url: elements.baseUrl.value.trim(),
    api_key: elements.apiKey.value.trim(),
    model: elements.model.value.trim(),
  };
}

function loadSettings() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return;
  try {
    const settings = JSON.parse(saved);
    elements.baseUrl.value = settings.baseUrl || elements.baseUrl.value;
    elements.apiKey.value = settings.apiKey || "";
    elements.model.value = settings.model || "";
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  button.dataset.originalLabel ||= button.textContent;
  button.textContent = busy ? label : button.dataset.originalLabel;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "请求失败，请稍后重试。");
  return data;
}

function renderResults(data) {
  elements.results.hidden = false;
  elements.resultTable.replaceChildren();
  const headerRow = document.createElement("tr");
  data.columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.textContent = column;
    headerRow.append(cell);
  });
  const thead = document.createElement("thead");
  thead.append(headerRow);
  const tbody = document.createElement("tbody");
  data.rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value === null ? "NULL" : String(value);
      tr.append(td);
    });
    tbody.append(tr);
  });
  elements.resultTable.append(thead, tbody);
  elements.resultMeta.textContent = data.rows.length
    ? `返回 ${data.row_count} 行${data.truncated ? "（结果已截断为前 200 行）" : ""}`
    : "查询没有返回记录。";
}

elements.settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const provider = providerFromForm();
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    baseUrl: provider.base_url,
    apiKey: provider.api_key,
    model: provider.model,
  }));
  elements.settingsMessage.textContent = "设置已保存到当前浏览器。";
});

elements.clearSettings.addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  elements.apiKey.value = "";
  elements.model.value = "";
  elements.settingsMessage.textContent = "浏览器保存的设置已清除。";
});

elements.toggleSettings.addEventListener("click", () => {
  const collapsed = elements.settingsForm.hidden;
  elements.settingsForm.hidden = !collapsed;
  elements.toggleSettings.textContent = collapsed ? "收起" : "展开";
  elements.toggleSettings.setAttribute("aria-expanded", String(collapsed));
});

elements.questionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFeedback();
  elements.results.hidden = true;
  const provider = providerFromForm();
  if (!provider.base_url || !provider.api_key || !provider.model) {
    showFeedback("请先填写并保存 Base URL、API Key 和模型名称。", "error");
    return;
  }
  setBusy(elements.generateButton, true, "正在生成…");
  try {
    const data = await requestJson("/api/generate-sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: elements.question.value.trim(), provider }),
    });
    elements.sql.value = data.sql;
    elements.executeButton.disabled = false;
    showFeedback(data.message, "success");
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setBusy(elements.generateButton, false);
  }
});

elements.executeButton.addEventListener("click", async () => {
  clearFeedback();
  const sql = elements.sql.value.trim();
  if (!sql) {
    showFeedback("请先生成或输入 SQL。", "error");
    return;
  }
  setBusy(elements.executeButton, true, "正在执行…");
  try {
    const data = await requestJson("/api/execute-sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql }),
    });
    renderResults(data);
    showFeedback("查询已执行。", "success");
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setBusy(elements.executeButton, false);
  }
});

elements.copySql.addEventListener("click", async () => {
  if (!elements.sql.value.trim()) {
    showFeedback("没有可复制的 SQL。", "error");
    return;
  }
  await navigator.clipboard.writeText(elements.sql.value);
  showFeedback("SQL 已复制到剪贴板。", "success");
});

loadSettings();
```

- [ ] **Step 3: Add focused responsive visual styling**

Create `app/static/styles.css`:

```css
:root {
  color-scheme: light;
  font-family: "Microsoft YaHei", "Noto Sans SC", sans-serif;
  background: #f5f7fb;
  color: #172033;
}

* { box-sizing: border-box; }
body { margin: 0; }
button, input, textarea { font: inherit; }
button { cursor: pointer; }

.app-shell { width: min(100% - 32px, 980px); margin: 0 auto; padding: 48px 0 72px; }
.hero { margin-bottom: 28px; }
.eyebrow { color: #2d5bce; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; font-size: .76rem; }
h1 { margin: 4px 0 8px; font-size: clamp(2.4rem, 7vw, 4.6rem); letter-spacing: -.06em; }
h2 { margin: 0; font-size: 1.1rem; }
.panel { margin-top: 18px; padding: 22px; border: 1px solid #dbe2ef; border-radius: 16px; background: white; box-shadow: 0 14px 32px rgba(27, 44, 77, .06); }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.wide { grid-column: 1 / -1; }
label { display: grid; gap: 7px; font-size: .9rem; font-weight: 700; }
input, textarea { width: 100%; border: 1px solid #bac6dc; border-radius: 9px; padding: 11px 12px; background: #fbfcff; color: inherit; }
textarea { resize: vertical; line-height: 1.5; }
#sql { font-family: Consolas, "Cascadia Code", monospace; }
input:focus, textarea:focus { outline: 3px solid rgba(45, 91, 206, .18); border-color: #2d5bce; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
button { border: 0; border-radius: 9px; padding: 10px 15px; background: #2452c7; color: white; font-weight: 700; }
button:hover { background: #1d45a8; }
button:disabled { cursor: not-allowed; opacity: .55; }
button.secondary, .text-button { background: #e8edf7; color: #263551; }
button.text-button { padding: 7px 10px; }
.hint { margin: 0; color: #5d6a81; font-size: .86rem; line-height: 1.5; }
.feedback { margin-top: 18px; padding: 13px 16px; border-radius: 10px; font-weight: 600; }
.feedback.success { background: #e7f7ee; color: #16653d; }
.feedback.error { background: #fceded; color: #a12828; }
.feedback.info { background: #eaf1ff; color: #244b9e; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .92rem; }
th, td { padding: 11px 12px; border-bottom: 1px solid #e1e6f0; text-align: left; white-space: nowrap; }
th { background: #f3f6fc; }

@media (max-width: 640px) {
  .app-shell { width: min(100% - 20px, 980px); padding-top: 28px; }
  .panel { padding: 16px; border-radius: 12px; }
  .settings-grid { grid-template-columns: 1fr; }
  .wide { grid-column: auto; }
}
```

- [ ] **Step 4: Run the application and manually verify the browser flow**

Run:

```bash
python -m uvicorn app.main:app --reload
```

Expected: Uvicorn reports it is listening at `http://127.0.0.1:8000`.

Manually verify in a browser:

1. Visit `http://127.0.0.1:8000` and confirm the page loads.
2. Save sample settings and refresh; Base URL, Key, and model remain populated.
3. Clear settings and refresh; Key and model are blank.
4. Enter a question with missing settings; confirm a visible error appears without clearing the question.
5. Paste `SELECT name FROM customers` into SQL and click execution; confirm the table renders.
6. Paste `DELETE FROM orders`; confirm the UI shows the server safety error and the database remains unchanged.

Stop Uvicorn with `Ctrl+C` after verification.

- [ ] **Step 5: Commit the UI**

Run:

```bash
git add app/static
git commit -m "feat: add sqlbot browser interface"
```

Expected: one commit containing the static single-page client.

## Task 6: Document local usage and run the complete verification suite

**Files:**
- Create: `README.md`
- Modify: `tests/test_api.py` (add static-page smoke coverage)

**Interfaces:**
- Consumes: the complete application and test suite from Tasks 1–5.
- Produces: reproducible setup, run, test, and safety documentation for a new developer.

- [ ] **Step 1: Add a static-page smoke test before documenting it**

Append to `tests/test_api.py`:

```python

def test_root_serves_sqlbot_page(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "<title>SQLbot</title>" in response.text
    assert 'id="generate-button"' in response.text
```

- [ ] **Step 2: Run the smoke test to verify it passes**

Run:

```bash
python -m pytest tests/test_api.py::test_root_serves_sqlbot_page -v
```

Expected: `1 passed`.

- [ ] **Step 3: Write the project README**

Create `README.md`:

```markdown
# SQLbot

SQLbot 是一个本地运行的 MVP：把自然语言问题转换为 SQLite 查询 SQL，展示给用户确认或编辑后，再安全执行并显示结果。

## 功能

- 内置电商 SQLite 示例库：`customers`、`products`、`orders`、`order_items`。
- 支持 OpenAI Chat Completions 兼容接口。
- 页面保存 Base URL、API Key 和模型名称到当前浏览器的 localStorage。
- SQL 生成后不会自动执行；用户可修改 SQL 后再查询。
- 后端仅允许单条只读 `SELECT` 或 `WITH ... SELECT` 查询。
- 后端限制最大返回 200 行，并用 SQLite authorizer 再次阻止写入操作。

## 前置条件

- Python 3.11 或更高版本。
- 一个可用的 OpenAI Chat Completions 兼容服务。服务必须实现：
  `POST {Base URL}/chat/completions`。

## 安装

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows Git Bash:
# source .venv/Scripts/activate
pip install -r requirements.txt
```

## 启动

```bash
python -m uvicorn app.main:app --reload
```

在浏览器打开 <http://127.0.0.1:8000>。

首次启动会自动创建 `data/demo.db`。该文件是运行时示例数据，不会提交到 Git；删除它后再次启动即可重新生成。

## 使用方式

1. 在“模型设置”填入 API Base URL、API Key 和模型名称，例如：
   - Base URL：`https://api.openai.com/v1`
   - 模型：由你的服务提供商决定
2. 点击“保存设置”。设置保存在浏览器 localStorage，刷新页面后仍可使用。
3. 输入问题，例如“查询销售额最高的 5 个商品”。
4. 点击“生成 SQL”。
5. 检查或手动编辑 SQL，然后点击“执行查询”。

> API Key 不会被服务端持久化，但浏览器 localStorage 不适合多人共用机器或生产环境。使用后可点击“清除配置”。

## 安全范围

SQLbot MVP 只服务于内置 SQLite 示例库，并且仅接受单条只读查询：

- 允许：`SELECT`、`WITH ... SELECT`。
- 拒绝：`INSERT`、`UPDATE`、`DELETE`、`CREATE`、`DROP`、`ALTER`、`PRAGMA`、`ATTACH`、事务控制和多语句 SQL。
- 即使通过前端绕过，后端仍会校验 SQL，并通过 SQLite authorizer 拒绝写操作。

这不是用于生产数据库的权限系统。不要把真实生产数据库或高权限凭据接入本 MVP。

## 测试

测试不访问模型服务，也不需要 API Key：

```bash
python -m pytest -v
```

## 后续方向

可在 MVP 验证后逐步加入 Schema 浏览器、查询历史、CSV 导出、多轮对话、MySQL/PostgreSQL 只读连接和服务器端密钥管理。
```

- [ ] **Step 4: Run the complete automated verification suite**

Run:

```bash
python -m pytest -v
```

Expected: every test passes, including seed creation, SQL validation, read-only execution, API behavior, and static page serving.

- [ ] **Step 5: Perform one final manual safety check using the live server**

Run:

```bash
python -m uvicorn app.main:app --port 8000
```

In a separate shell, run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/execute-sql \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT COUNT(*) AS order_count FROM orders"}'

curl -s -X POST http://127.0.0.1:8000/api/execute-sql \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT 1; DELETE FROM orders"}'
```

Expected:

- The first response is HTTP 200 JSON with `columns`, `rows`, `row_count`, and `truncated`.
- The second response is HTTP 422 JSON whose `detail` identifies the read-only SQL restriction.

Stop Uvicorn with `Ctrl+C`.

- [ ] **Step 6: Commit documentation and final tests**

Run:

```bash
git add README.md tests/test_api.py
git commit -m "docs: add sqlbot setup and safety guide"
git status --short
```

Expected: the documentation and smoke test are committed; `git status --short` produces no output.

## Spec Coverage Review

- OpenAI-compatible generation: Task 4.
- FastAPI same-origin API and static web page: Tasks 4 and 5.
- SQLite demo schema and seed data: Task 1.
- Dynamic schema prompt context: Tasks 3 and 4.
- User-confirmed, editable SQL execution: Task 5.
- `SELECT` / `WITH ... SELECT` only, no writes, no DDL, no multi-statements: Tasks 2–4.
- Read-only SQLite execution, row bound, and result metadata: Task 3.
- localStorage provider settings, clearing behavior, and no server persistence: Task 5 and README in Task 6.
- Clear error presentation without retry or synthetic SQL: Tasks 4 and 5.
- Automated unit/integration tests without external model credentials: Tasks 1–4 and 6.

## Plan Self-Review

- Scope is a single independently runnable MVP; no separate subsystem plan is required.
- All planned files have one defined responsibility and all later interfaces are introduced by earlier tasks.
- No `TBD`, `TODO`, deferred implementation, or unspecified test steps remain.
- The design specification’s requirements are mapped to implementation tasks above.
