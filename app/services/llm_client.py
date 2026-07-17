from __future__ import annotations

import re

import httpx

from app.api.schemas import ProviderConfig


class LLMServiceError(RuntimeError):
    """Raised when the configured compatible model service cannot generate SQL."""


SYSTEM_PROMPT_TEMPLATE = """你是 SQLite 数据分析助手。根据用户问题生成 SQL。

可用数据库 Schema：
{schema_summary}

严格规则：
1. 只返回一条 SQLite SQL 查询。
2. 只允许 SELECT 或 WITH ... SELECT。
3. 只能使用给定的表和字段。
4. 不要解释，不要 Markdown，不要代码块。
5. 对可能返回很多行的查询使用合理的 LIMIT。
"""


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def extract_sql(model_text: str) -> str:
    stripped = model_text.strip()
    fenced = re.fullmatch(
        r"```(?:sql)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL
    )
    return fenced.group(1).strip() if fenced else stripped


def generate_sql(provider: ProviderConfig, question: str, schema_summary: str) -> str:
    payload = {
        "model": provider.model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_TEMPLATE.format(schema_summary=schema_summary),
            },
            {"role": "user", "content": question},
        ],
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                _chat_completions_url(provider.base_url),
                headers={"Authorization": f"Bearer {provider.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise LLMServiceError(
            "模型服务调用失败，请检查 Base URL、API Key、模型名称和网络连接。"
        ) from error

    if not isinstance(content, str) or not content.strip():
        raise LLMServiceError("模型服务没有返回可用的 SQL。")
    return extract_sql(content)
