from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import (
    ExecuteSQLRequest,
    ExecuteSQLResponse,
    GenerateSQLRequest,
    GenerateSQLResponse,
)
from app.services.llm_client import LLMServiceError, extract_sql, generate_sql
from app.services.query_executor import QueryExecutionError, execute_readonly_query
from app.services.schema_reader import get_schema_summary
from app.services.sql_guard import SQLValidationError, validate_readonly_sql


router = APIRouter(prefix="/api")


@router.post("/generate-sql", response_model=GenerateSQLResponse)
def generate_sql_route(
    payload: GenerateSQLRequest, request: Request
) -> GenerateSQLResponse:
    db_path = request.app.state.db_path
    schema_summary = get_schema_summary(db_path)
    generator = request.app.state.llm_generate
    try:
        sql = validate_readonly_sql(
            extract_sql(generator(payload.provider, payload.question, schema_summary))
        )
    except LLMServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except SQLValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=f"生成的 SQL 未通过只读安全校验：{error}",
        ) from error

    return GenerateSQLResponse(
        sql=sql,
        schema_summary=schema_summary,
        message="SQL 已生成，请确认后执行。",
    )


@router.post("/execute-sql", response_model=ExecuteSQLResponse)
def execute_sql_route(
    payload: ExecuteSQLRequest, request: Request
) -> ExecuteSQLResponse:
    try:
        result = execute_readonly_query(request.app.state.db_path, payload.sql)
    except SQLValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=f"SQL 未通过只读安全校验：{error}",
        ) from error
    except QueryExecutionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return ExecuteSQLResponse(
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
    )
