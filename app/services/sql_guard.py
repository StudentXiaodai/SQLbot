from __future__ import annotations


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
        if char in ('\"', "`"):
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
        if char in ('\"', "`"):
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
