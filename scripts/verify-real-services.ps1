param(
    [switch]$StartInfra,
    [string]$ComposeFile = "resources/docker/python-infra.compose.yaml",
    [string]$BackendDir = "python-backend",
    [string]$DatabaseUrl = "postgresql+asyncpg://postgres:postgres@localhost:5432/ragent",
    [string]$RedisUrl = "redis://localhost:6379/0",
    [string]$MilvusUri = "http://localhost:19530",
    [string]$RocketMQNameServer = "localhost:9876",
    [int]$ServiceWarmupSeconds = 20,
    [int]$RocketMQTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComposePath = Join-Path $RepoRoot $ComposeFile
$BackendPath = Join-Path $RepoRoot $BackendDir

if ($StartInfra) {
    Write-Host "==> 启动真实服务基础设施"
    docker compose -f $ComposePath up -d
    Write-Host "==> 等待服务预热 $ServiceWarmupSeconds 秒"
    Start-Sleep -Seconds $ServiceWarmupSeconds
    docker compose -f $ComposePath ps
}

Write-Host "==> 配置真实服务联调环境变量"
$env:REAL_SERVICES_SMOKE_ENABLED = "true"
$env:MILVUS_INTEGRATION_ENABLED = "true"
$env:DATABASE_URL = $DatabaseUrl
$env:REDIS_URL = $RedisUrl
$env:RAG_VECTOR_TYPE = "milvus"
$env:MILVUS_URI = $MilvusUri
$env:RAG_TASK_QUEUE_BACKEND = "rocketmq"
$env:ROCKETMQ_NAME_SERVER = $RocketMQNameServer
$env:ROCKETMQ_PRODUCER_GROUP = "ragent-python-producer"
$env:ROCKETMQ_CONSUMER_GROUP = "ragent-python-consumer"
$env:ROCKETMQ_TOPIC = "ragent-python-task-smoke"
$env:ROCKETMQ_DLQ_TOPIC = "ragent-python-task-smoke.DLQ"
$env:REAL_SERVICES_ROCKETMQ_TIMEOUT_SECONDS = "$RocketMQTimeoutSeconds"

Write-Host "==> 运行 PostgreSQL + Redis + Milvus + RocketMQ + MCP + Alembic 真实冒烟测试"
Push-Location $BackendPath
try {
    python -m pytest `
        tests\test_real_services_smoke.py `
        tests\test_milvus_integration.py `
        -m integration `
        -q
}
finally {
    Pop-Location
}

Write-Host "==> 真实服务联调验证通过"
