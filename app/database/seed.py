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
