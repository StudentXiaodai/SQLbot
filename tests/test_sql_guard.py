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
