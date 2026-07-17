from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1, max_length=1000)
    model: str = Field(min_length=1, max_length=200)


class GenerateSQLRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    provider: ProviderConfig


class ExecuteSQLRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10000)


class GenerateSQLResponse(BaseModel):
    sql: str
    schema_summary: str
    message: str


class ExecuteSQLResponse(BaseModel):
    columns: list[str]
    rows: list[list[object]]
    row_count: int
    truncated: bool
