# SQLbot

SQLbot 是一个本地运行的 MVP：把自然语言问题转换为 SQLite 查询 SQL，展示给用户确认或编辑后，再安全执行并显示结果。

## 功能

- 内置电商 SQLite 示例库：`customers`、`products`、`orders`、`order_items`。
- 支持 OpenAI Chat Completions 兼容接口。
- 页面保存 Base URL、API Key 和模型名称到当前浏览器的 localStorage。
- SQL 生成后不会自动执行；用户可修改 SQL 后再查询。
- 后端仅允许单条只读 `SELECT` 或 `WITH ... SELECT` 查询。
- 后端限制最大返回 200 行，并用 SQLite authorizer 再次阻止写入操作。

## 前置条件

- Python 3.11 或更高版本。
- 一个可用的 OpenAI Chat Completions 兼容服务。服务必须实现：
  `POST {Base URL}/chat/completions`。

## 安装

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows Git Bash:
# source .venv/Scripts/activate
pip install -r requirements.txt
```

## 启动

```bash
python -m uvicorn app.main:app --reload
```

在浏览器打开 <http://127.0.0.1:8000>。

首次启动会自动创建 `data/demo.db`。该文件是运行时示例数据，不会提交到 Git；删除它后再次启动即可重新生成。

## 使用方式

1. 在“模型设置”填入 API Base URL、API Key 和模型名称，例如：
   - Base URL：`https://api.openai.com/v1`
   - 模型：由你的服务提供商决定
2. 点击“保存设置”。设置保存在浏览器 localStorage，刷新页面后仍可使用。
3. 输入问题，例如“查询销售额最高的 5 个商品”。
4. 点击“生成 SQL”。
5. 检查或手动编辑 SQL，然后点击“执行查询”。

> API Key 不会被服务端持久化，但浏览器 localStorage 不适合多人共用机器或生产环境。使用后可点击“清除配置”。

## 安全范围

SQLbot MVP 只服务于内置 SQLite 示例库，并且仅接受单条只读查询：

- 允许：`SELECT`、`WITH ... SELECT`。
- 拒绝：`INSERT`、`UPDATE`、`DELETE`、`CREATE`、`DROP`、`ALTER`、`PRAGMA`、`ATTACH`、事务控制和多语句 SQL。
- 即使通过前端绕过，后端仍会校验 SQL，并通过 SQLite authorizer 拒绝写操作。

这不是用于生产数据库的权限系统。不要把真实生产数据库或高权限凭据接入本 MVP。

## 测试

测试不访问模型服务，也不需要 API Key：

```bash
python -m pytest -v
```

## 后续方向

可在 MVP 验证后逐步加入 Schema 浏览器、查询历史、CSV 导出、多轮对话、MySQL/PostgreSQL 只读连接和服务器端密钥管理。
