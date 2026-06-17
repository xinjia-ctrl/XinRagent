$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "==> 后端测试"
Push-Location (Join-Path $RepoRoot "python-backend")
try {
    python -m pytest
}
finally {
    Pop-Location
}

Write-Host "==> 前端类型检查、Lint 和构建"
Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm run typecheck
    npm run lint
    npm run build
}
finally {
    Pop-Location
}

Write-Host "==> 验证通过"
