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
