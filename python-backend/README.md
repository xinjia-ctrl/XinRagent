# Ragent Python 后端

Ragent Python 后端是基于 FastAPI 的异步 API 服务，用于承接原 Ragent 项目的登录鉴权、知识库管理、文档入库、向量检索、SSE 流式聊天和 RAG Trace 查询能力。

当前阶段重点是完成后端工程底座和 RAG 最小闭环，业务实现按《Python版本改造计划书.md》逐步迁移。

## 功能特性

- 健康检查接口：`GET /health`
- 统一响应结构与全局异常处理
- JWT 登录、退出和当前用户接口
- SQLAlchemy 异步数据库连接配置
- 用户、会话消息、知识库、文档分块、意图和 Trace 模型
- 基础 Repository 数据访问层
- OpenAI 风格聊天、Embedding、Rerank 抽象与模型路由
- SSE 流式聊天接口和回答停止接口
- pgvector 全局向量检索通道
- Markdown、TXT 文档上传、解析、分块与向量索引
- 知识库、文档、分块和 RAG Trace 后台查询接口

## 技术栈

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic v2
- pydantic-settings
- SQLAlchemy 2.x
- asyncpg
- Alembic
- pytest

## 环境要求

- Python 3.11 或更高版本
- PostgreSQL，需启用 `pgvector` 扩展
- 可选：Redis，后续任务调度或缓存能力使用
- 可选：兼容 OpenAI 协议的聊天和 Embedding 服务

## 安装与启动

在 Windows PowerShell 中执行：

```powershell
cd D:\XinRagent\python-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
uvicorn app.main:app --reload --port 9090
```

启动后访问：

```text
GET http://localhost:9090/health
```

预期返回：

```json
{"status":"ok"}
```

## 配置说明

项目使用环境变量或 `.env` 文件加载配置。常用配置如下：

```env
APP_NAME=ragent-python
APP_ENV=dev
APP_PORT=9090
API_PREFIX=/api/ragent

DATABASE_URL=postgresql+asyncpg://postgres:postgres@192.168.100.128:5432/XinRagent
REDIS_URL=redis://localhost:6379/0

AUTH_SECRET_KEY=ragent-dev-secret
AUTH_TOKEN_EXPIRE_SECONDS=86400

RAG_DEFAULT_COLLECTION_NAME=rag_default_store
RAG_DEFAULT_DIMENSION=1536
RAG_DEFAULT_TOP_K=5
INGESTION_STORAGE_DIR=storage/uploads

AI_BAILIAN_URL=https://dashscope.aliyuncs.com
AI_BAILIAN_API_KEY=
AI_SILICONFLOW_URL=https://api.siliconflow.cn
AI_SILICONFLOW_API_KEY=
AI_OLLAMA_URL=http://localhost:11434

AI_CHAT_DEFAULT_MODEL=qwen3-max
AI_EMBEDDING_DEFAULT_MODEL=qwen-emb-8b
AI_RERANK_DEFAULT_MODEL=qwen3-rerank
```

如果本地没有真实模型服务，建议在测试中继续使用 mock，不要让单元测试调用外部模型。

## 常用命令

```powershell
# 启动开发服务
uvicorn app.main:app --reload --port 9090

# 运行测试
python -m pytest

# 只运行 RAG 相关测试
python -m pytest tests\test_rag_chat_api.py tests\test_rag_vector_chain.py
```

## 项目结构

```text
python-backend/
  app/
    api/            # FastAPI 路由与依赖
    common/         # 通用工具
    core/           # 配置、响应、异常、安全、日志、请求上下文
    db/             # 异步数据库连接
    infra_ai/       # 聊天、Embedding、Rerank 与模型路由
    ingestion/      # 文档上传、解析、分块、索引
    models/         # SQLAlchemy ORM 模型
    rag/            # 流式任务、Prompt、检索、Pipeline
    repositories/   # 基础数据访问层
    schemas/        # Pydantic 请求与响应模型
    services/       # 业务服务
    main.py         # 应用入口
  tests/            # pytest 测试
  pyproject.toml
```

## 接口概览

基础接口：

- `GET /health`
- `POST /api/ragent/auth/login`
- `POST /api/ragent/auth/logout`
- `GET /api/ragent/user/me`

RAG 聊天：

- `GET /api/ragent/rag/v3/chat?question=...`
- `POST /api/ragent/rag/v3/chat`
- `POST /api/ragent/rag/v3/stop`

知识库与文档：

- `GET /api/ragent/knowledge-base`
- `POST /api/ragent/knowledge-base`
- `PUT /api/ragent/knowledge-base/{kb_id}`
- `DELETE /api/ragent/knowledge-base/{kb_id}`
- `POST /api/ragent/knowledge-base/{kb_id}/docs/upload`
- `GET /api/ragent/knowledge-base/{kb_id}/docs`
- `GET /api/ragent/knowledge-base/docs/{doc_id}`
- `GET /api/ragent/knowledge-base/docs/{doc_id}/chunks`

Trace：

- `GET /api/ragent/rag/traces/runs`
- `GET /api/ragent/rag/traces/runs/{trace_id}`

## 测试说明

执行完整测试：

```powershell
cd D:\XinRagent\python-backend
python -m pytest
```

测试中 AI 调用、流式聊天、文档入库和后台管理接口均使用 fake 或 mock 对象，避免依赖外部模型服务。

如果 Windows 环境出现 `.pytest_cache` 权限 warning，只要测试结果为 passed，不影响当前验证。

## 开发说明

- 新增接口时优先使用 `app.core.responses.ApiResponse` 保持统一响应结构。
- 业务异常使用 `RagentException`，让全局异常处理器转换为统一 JSON。
- 数据库访问优先通过 Repository 或 Service 封装，避免在路由中堆 SQL。
- RAG、AI、文档入库相关测试必须 mock 外部模型服务。
- 提交时按阶段拆分 commit，避免把 `resources/`、运行缓存或临时文件带入提交。
