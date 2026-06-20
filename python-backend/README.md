# Ragent Python 后端

Ragent Python 后端是基于 FastAPI 的异步 API 服务，用于承接原 Ragent 项目的登录鉴权、知识库管理、文档入库、向量检索、SSE 流式聊天和 RAG Trace 查询能力。

当前阶段已完成与原版前端主要服务接口的对齐，覆盖登录鉴权、用户、会话聊天、知识库、文档分块、入库流水线、意图树、查询词映射、示例问题、Trace、仪表盘和系统设置。

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
- 入库流水线、入库任务和任务节点管理接口
- 意图树、查询词映射、示例问题后台管理接口
- 后台仪表盘和系统设置查询接口
- 前端接口路由覆盖测试和第十天联调验证脚本

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
RAG_QUEUE_LIMIT_ENABLED=false
RAG_MCP_SERVERS=
MCP_HOST=0.0.0.0
MCP_PORT=9091
INGESTION_STORAGE_DIR=storage/uploads

RAG_TASK_QUEUE_BACKEND=memory
ROCKETMQ_NAME_SERVER=localhost:9876
ROCKETMQ_PRODUCER_GROUP=ragent-python-producer
ROCKETMQ_CONSUMER_GROUP=ragent-python-consumer
ROCKETMQ_TOPIC=ragent-python-task
ROCKETMQ_DLQ_TOPIC=ragent-python-task.DLQ
ROCKETMQ_MAX_CONSUME_ATTEMPTS=3

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

# 单独启动 MCP JSON-RPC 工具服务
ragent-mcp-server

# 运行测试
python -m pytest

# 只运行 RAG 相关测试
python -m pytest tests\test_rag_chat_api.py tests\test_rag_vector_chain.py

# 查看数据库迁移头
python -m alembic heads

# 初始化或升级 PostgreSQL 数据库结构
python -m alembic upgrade head

# 从仓库根目录运行第十天联调验证
cd D:\XinRagent
powershell -ExecutionPolicy Bypass -File scripts\verify-day10.ps1

# 只验证前端类型、Lint 和生产构建
cd D:\XinRagent\frontend
npm run build
```

## 项目结构

```text
python-backend/
  alembic/          # Alembic 数据库迁移脚本
  app/
    api/            # FastAPI 路由与依赖
    common/         # 通用工具
    core/           # 配置、响应、异常、安全、日志、请求上下文
    db/             # 异步数据库连接
    infra_ai/       # 聊天、Embedding、Rerank 与模型路由
    ingestion/      # 文档上传、解析、分块、索引
    mcp/            # MCP JSON-RPC 服务、客户端、工具注册与参数提取
    models/         # SQLAlchemy ORM 模型
    rag/            # 流式任务、Prompt、检索、Pipeline
    repositories/   # 基础数据访问层
    schemas/        # Pydantic 请求与响应模型
    services/       # 业务服务
    main.py         # 应用入口
  tests/            # pytest 测试
  pyproject.toml
```

数据库初始化 SQL 位于 `resources/database/schema_pg.sql`，当前 Alembic 初始迁移会复用该 PostgreSQL 脚本作为权威建表来源。

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
- `GET /api/ragent/rag/sample-questions`
- `GET /api/ragent/rag/settings`

知识库与文档：

- `GET /api/ragent/knowledge-base`
- `POST /api/ragent/knowledge-base`
- `PUT /api/ragent/knowledge-base/{kb_id}`
- `DELETE /api/ragent/knowledge-base/{kb_id}`
- `POST /api/ragent/knowledge-base/{kb_id}/docs/upload`
- `GET /api/ragent/knowledge-base/{kb_id}/docs`
- `GET /api/ragent/knowledge-base/docs/search`
- `GET /api/ragent/knowledge-base/docs/{doc_id}`
- `PUT /api/ragent/knowledge-base/docs/{doc_id}`
- `POST /api/ragent/knowledge-base/docs/{doc_id}/chunk`
- `PATCH /api/ragent/knowledge-base/docs/{doc_id}/enable`
- `DELETE /api/ragent/knowledge-base/docs/{doc_id}`
- `GET /api/ragent/knowledge-base/docs/{doc_id}/chunks`
- `POST /api/ragent/knowledge-base/docs/{doc_id}/chunks`
- `PUT /api/ragent/knowledge-base/docs/{doc_id}/chunks/{chunk_id}`
- `DELETE /api/ragent/knowledge-base/docs/{doc_id}/chunks/{chunk_id}`
- `PATCH /api/ragent/knowledge-base/docs/{doc_id}/chunks/{chunk_id}/enable`
- `PATCH /api/ragent/knowledge-base/docs/{doc_id}/chunks/batch-enable`
- `GET /api/ragent/knowledge-base/docs/{doc_id}/chunk-logs`

入库流水线：

- `GET /api/ragent/ingestion/pipelines`
- `POST /api/ragent/ingestion/pipelines`
- `GET /api/ragent/ingestion/pipelines/{pipeline_id}`
- `PUT /api/ragent/ingestion/pipelines/{pipeline_id}`
- `DELETE /api/ragent/ingestion/pipelines/{pipeline_id}`
- `GET /api/ragent/ingestion/tasks`
- `POST /api/ragent/ingestion/tasks`
- `POST /api/ragent/ingestion/tasks/upload`
- `GET /api/ragent/ingestion/tasks/{task_id}`
- `GET /api/ragent/ingestion/tasks/{task_id}/nodes`

RAG 管理：

- `GET /api/ragent/intent-tree/trees`
- `POST /api/ragent/intent-tree`
- `PUT /api/ragent/intent-tree/{node_id}`
- `DELETE /api/ragent/intent-tree/{node_id}`
- `POST /api/ragent/intent-tree/batch/enable`
- `POST /api/ragent/intent-tree/batch/disable`
- `POST /api/ragent/intent-tree/batch/delete`
- `GET /api/ragent/mappings`
- `POST /api/ragent/mappings`
- `PUT /api/ragent/mappings/{mapping_id}`
- `DELETE /api/ragent/mappings/{mapping_id}`
- `GET /api/ragent/sample-questions`
- `POST /api/ragent/sample-questions`
- `PUT /api/ragent/sample-questions/{question_id}`
- `DELETE /api/ragent/sample-questions/{question_id}`

Trace：

- `GET /api/ragent/rag/traces/runs`
- `GET /api/ragent/rag/traces/runs/{trace_id}`
- `GET /api/ragent/rag/traces/runs/{trace_id}/nodes`

后台仪表盘：

- `GET /api/ragent/admin/dashboard/overview`
- `GET /api/ragent/admin/dashboard/performance`
- `GET /api/ragent/admin/dashboard/trends`
- `GET /api/ragent/admin/ai/model-health`
- `POST /api/ragent/admin/ai/model-health/probe`

独立 MCP 服务：

- `POST /mcp`

## 测试说明

执行完整测试：

```powershell
cd D:\XinRagent\python-backend
python -m pytest
```

执行前后端联调验证：

```powershell
cd D:\XinRagent
powershell -ExecutionPolicy Bypass -File scripts\verify-day10.ps1
```

测试中 AI 调用、流式聊天、文档入库和后台管理接口均使用 fake 或 mock 对象，避免依赖外部模型服务。

`tests\test_frontend_contract_routes.py` 会检查原版前端服务依赖的核心接口是否已在 FastAPI 路由表注册。新增前端接口时，需要同步更新该测试，防止后端遗漏契约。

如果 Windows 环境出现 `.pytest_cache` 权限 warning，只要测试结果为 passed，不影响当前验证。

## 开发说明

- 新增接口时优先使用 `app.core.responses.ApiResponse` 保持统一响应结构。
- 业务异常使用 `RagentException`，让全局异常处理器转换为统一 JSON。
- 数据库访问优先通过 Repository 或 Service 封装，避免在路由中堆 SQL。
- RAG、AI、文档入库相关测试必须 mock 外部模型服务。
- 提交时按阶段拆分 commit，避免把 `resources/`、运行缓存或临时文件带入提交。
