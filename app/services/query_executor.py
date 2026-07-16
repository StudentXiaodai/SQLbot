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


def _readonly_authorizer(
    action_code: int,
    _arg1: str | None,
    _arg2: str | None,
    _db: str | None,
    _trigger: str | None,
) -> int:
    if action_code in DENIED_AUTHORIZER_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def execute_readonly_query(
    db_path: Path, sql: str, max_rows: int = 200
) -> QueryResult:
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
