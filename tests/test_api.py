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
    return {"base_url": "https://example.test/v1", "api_key": "test-key", "model": "test-model"}


def test_generate_sql_passes_schema_to_llm_and_returns_unexecuted_sql(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    captured: dict[str, str] = {}

    def fake_generate(provider, question, schema):
        captured["question"] = question
        captured["schema"] = schema
        return "```sql\nSELECT name FROM customers\n```"

    client.app.state.llm_generate = fake_generate
    response = client.post("/api/generate-sql", json={"question": "列出所有客户", "provider": provider_payload()})
    assert response.status_code == 200
    assert response.json()["sql"] == "SELECT name FROM customers"
    assert response.json()["message"] == "SQL 已生成，请确认后执行。"
    assert captured["question"] == "列出所有客户"
    assert "TABLE customers" in captured["schema"]


def test_generate_sql_rejects_unsafe_model_output(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.app.state.llm_generate = lambda provider, question, schema: "DELETE FROM orders"
    response = client.post("/api/generate-sql", json={"question": "删除订单", "provider": provider_payload()})
    assert response.status_code == 422
    assert "只读" in response.json()["detail"]


def test_execute_sql_returns_tabular_data(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/execute-sql", json={"sql": "SELECT name, city FROM customers ORDER BY id LIMIT 2"})
    assert response.status_code == 200
    assert response.json() == {"columns": ["name", "city"], "rows": [["张三", "上海"], ["李四", "北京"]], "row_count": 2, "truncated": False}


def test_execute_sql_rejects_writes(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/api/execute-sql", json={"sql": "DELETE FROM orders"})
    assert response.status_code == 422
    assert "只读" in response.json()["detail"]
