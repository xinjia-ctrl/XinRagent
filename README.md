# XinRagent

XinRagent 是对开源项目 [nageoffer/ragent](https://github.com/nageoffer/ragent) 的 Python 语言版本改造与工程化复刻。本仓库不是上游官方仓库，而是在保留原项目 RAG / Agent / MCP 核心设计思路、前端接口习惯和数据库结构基础上，使用 FastAPI 重新实现后端，并补齐 Python 生态下的测试、迁移和联调资源。

原项目 Ragent 是一个企业级 Agentic RAG 平台，核心能力覆盖文档入库、智能问答、多路检索、意图识别、模型路由、MCP 集成和管理后台。本仓库的目标是把这些能力迁移为可运行、可测试、可持续演进的 Python 版本。

## 功能特性

- FastAPI 异步后端，统一响应、异常、日志、鉴权和请求上下文。
- React + Vite 前端，保持 `/api/ragent` 接口前缀和主要页面契约。
- PostgreSQL + pgvector 数据库结构，已接入 Alembic 迁移体系。
- RAG 流式问答链路：会话记忆、问题重写、意图识别、检索、rerank、Prompt 拼接、SSE 输出。
- 文档入库 ETL：上传、解析、分块、向量化、任务节点日志和可编排 Pipeline。
- AI 基础设施：OpenAI 风格 Chat / Embedding / Rerank、多模型路由、熔断、首 token 探测。
- 向量库双路线：pgvector 默认路线，Milvus collection / index / search / delete / rebuild 支持。
- MCP 能力：独立 JSON-RPC ASGI 服务、工具注册、远程工具发现、LLM 参数提取。
- 生产化补强：Redis 队列限流、RocketMQ 任务队列适配、幂等、Outbox、真实服务冒烟脚本。
- 后台管理接口：用户、知识库、文档、分块、入库、意图树、样例问题、映射、Trace、设置、仪表盘。

## 技术栈

- 后端：Python 3.11+、FastAPI、SQLAlchemy 2.x、Pydantic v2、Alembic、pytest
- 前端：React 18、TypeScript、Vite、Radix UI、Zustand、React Router
- 数据与中间件：PostgreSQL、pgvector、Redis、RocketMQ、Milvus、MinIO
- AI 接入：OpenAI-compatible API、百炼 / DashScope、SiliconFlow、Ollama

## 项目结构

```text
XinRagent/
  frontend/          # React 前端
  python-backend/    # Python FastAPI 后端
  resources/         # 数据库 SQL、Docker Compose 等工程资源
  scripts/           # 本地验证与真实服务联调脚本
  docs/              # 前端接口盘点和契约文档
```

## 环境要求

- Windows PowerShell
- Python 3.11 或更高版本
- Node.js 18 或更高版本
- PostgreSQL，推荐使用带 pgvector 的镜像
- 可选：Redis、Milvus、RocketMQ、MinIO、兼容 OpenAI 协议的模型服务

## 快速启动

后端：

```powershell
cd D:\XinRagent\python-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m alembic upgrade head
uvicorn app.main:app --reload --port 9090
```

前端：

```powershell
cd D:\XinRagent\frontend
npm install
npm run dev
```

默认访问地址：

- 后端健康检查：`http://127.0.0.1:9090/health`
- 前端开发服务：`http://127.0.0.1:5173`
- API 前缀：`/api/ragent`

## 配置说明

Python 后端通过环境变量或 `python-backend/.env` 读取配置。常用配置包括：

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ragent
REDIS_URL=redis://localhost:6379/0
RAG_VECTOR_TYPE=pg
RAG_TASK_QUEUE_BACKEND=memory
AI_BAILIAN_API_KEY=
AI_SILICONFLOW_API_KEY=
AI_OLLAMA_URL=http://localhost:11434
```

更完整的配置说明见 [python-backend/README.md](python-backend/README.md)。

## 常用命令

```powershell
# 后端单元测试
cd D:\XinRagent\python-backend
python -m pytest

# 前端类型检查、Lint、构建
cd D:\XinRagent\frontend
npm run typecheck
npm run lint
npm run build

# 前后端基础门禁
cd D:\XinRagent
powershell -ExecutionPolicy Bypass -File scripts\verify-day10.ps1

# 真实服务端到端冒烟测试
cd D:\XinRagent
powershell -ExecutionPolicy Bypass -File scripts\verify-real-services.ps1 -StartInfra
```

真实服务冒烟测试会覆盖 PostgreSQL、Redis、Milvus、RocketMQ、MCP 和 Alembic。普通测试默认不会连接这些外部服务。

## 开发说明

- 本仓库以 Python 版本复刻为目标，优先保持前端接口契约和数据库结构稳定。
- 后端新增数据库变更时，应优先新增 Alembic revision。
- 新增前端依赖接口时，需要同步更新后端路由测试和前端 parity 验收脚本。
- RAG、AI、入库和 MCP 相关能力优先补测试，真实模型和真实中间件调用放在显式联调脚本中执行。
- `resources/database/backups/` 仅用于本地备份或临时 dump，不应作为工程必需资料提交。

## 当前复刻状态

当前 Python 版已经完成核心 API、RAG 主链路、入库 ETL、数据库迁移、Milvus / pgvector、MCP、RocketMQ 适配和后台管理接口的主要复刻。仍建议继续补强真实服务 CI、前端浏览器级 E2E、生产部署资源、MCP 协议兼容测试和长期可观测性。

## 许可证与来源

本项目基于 [nageoffer/ragent](https://github.com/nageoffer/ragent) 的功能与架构进行 Python 化改造。使用、分发或二次开发前，请同时确认上游项目许可证、本仓库许可证以及相关依赖的授权要求。
