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
            foreign_keys = connection.execute(
                f'PRAGMA foreign_key_list("{table_name}")'
            ).fetchall()
            column_text = ", ".join(f"{column[1]} {column[2]}" for column in columns)
            lines.append(f"TABLE {table_name}: {column_text}")
            for foreign_key in foreign_keys:
                lines.append(
                    f"FOREIGN KEY {foreign_key[3]} -> {foreign_key[2]}.{foreign_key[4]}"
                )
    return "\n".join(lines)
