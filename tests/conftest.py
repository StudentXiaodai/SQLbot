from pathlib import Path

import pytest

from app.database.seed import create_demo_database


@pytest.fixture
def demo_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "demo.db"
    create_demo_database(db_path)
    return db_path
