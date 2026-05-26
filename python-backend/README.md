# Ragent Python 后端

这是 Ragent 的 Python 后端骨架，当前完成《Python版本改造计划书.md》中的阶段 0：FastAPI 项目初始化、基础配置加载、健康检查接口和最小测试。

## 技术栈

- FastAPI
- Uvicorn
- Pydantic v2
- pydantic-settings
- SQLAlchemy 2.x
- Alembic
- asyncpg
- pytest

## 环境要求

- Python 3.11+
- PostgreSQL 与 Redis 在后续阶段接入，当前健康检查不依赖外部服务

## 安装与启动

```powershell
cd D:\XinRagent\python-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
uvicorn app.main:app --reload --port 9090
```

健康检查：

```text
GET http://localhost:9090/health
```

返回：

```json
{"status":"ok"}
```

## 常用命令

```powershell
pytest
```

## 项目结构

```text
python-backend/
  app/
    main.py
    api/
    core/
    db/
    models/
    schemas/
    repositories/
    services/
    rag/
    ingestion/
    infra_ai/
    mcp/
    common/
  tests/
```

## 开发说明

当前只初始化后端骨架，不实现业务接口。后续阶段将按计划书逐步补齐基础设施、数据库模型、鉴权、AI 基础设施、RAG SSE 问答和文档入库能力。
