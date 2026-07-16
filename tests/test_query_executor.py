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
