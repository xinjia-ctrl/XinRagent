# Python 版基础设施

本目录提供 Python 后端本地/测试环境依赖的 Docker Compose 编排，覆盖 PostgreSQL + pgvector、Redis、RocketMQ、Milvus、Attu 和 RocketMQ Dashboard。

启动：

```powershell
docker compose -f resources/docker/python-infra.compose.yaml up -d
```

常用地址：

- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`
- RocketMQ NameServer：`localhost:9876`
- RocketMQ Dashboard：`http://localhost:8082`
- Milvus：`http://localhost:19530`
- Attu：`http://localhost:8000`

对应 Python 后端关键配置：

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ragent
REDIS_URL=redis://localhost:6379/0
RAG_TASK_QUEUE_BACKEND=redis
ROCKETMQ_NAME_SERVER=localhost:9876
RAG_VECTOR_TYPE=pg
MILVUS_URI=http://localhost:19530
```

需要验证 Milvus 或 RocketMQ 路线时，将 `RAG_VECTOR_TYPE` 改为 `milvus`，或将 `RAG_TASK_QUEUE_BACKEND` 改为 `rocketmq`，并安装生产可选依赖：

```powershell
pip install -e "python-backend[prod]"
```
