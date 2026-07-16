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
