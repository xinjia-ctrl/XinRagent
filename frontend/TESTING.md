# 快速测试指南

本文档用于在当前 Python 后端版本下验证前端代理和主要页面是否能正常联调。

## 环境端口

- Python 后端默认地址：`http://127.0.0.1:9090`
- 前端开发地址：`http://127.0.0.1:5173`
- 前端 API 前缀：`/api/ragent`

`vite.config.ts` 已将 `/api` 代理到 `VITE_API_PROXY_TARGET`，未配置时默认转发到 `http://127.0.0.1:9090`。

## 启动步骤

### 1. 启动后端

```powershell
cd D:\XinRagent\python-backend
uvicorn app.main:app --reload --port 9090
```

健康检查：

```powershell
curl http://127.0.0.1:9090/health
```

预期返回：

```json
{"status":"ok"}
```

### 2. 启动前端

```powershell
cd D:\XinRagent\frontend
npm run dev
```

打开浏览器访问：

```text
http://127.0.0.1:5173
```

## 登录与页面验证

1. 使用管理员账号登录。
2. 进入聊天页，发送一条问题，确认 SSE 流式响应可以正常返回。
3. 点击左侧用户入口进入管理后台。
4. 依次检查知识库、文档、数据通道、意图树、Trace、系统设置等页面是否能正常加载。

## 常见问题

**Q: 出现 `No static resource api/ragent/...` 怎么办？**

A: 通常是前端代理没有生效。确认后端运行在 `9090`，并重启前端开发服务器。

**Q: 后端 API 返回 401 怎么办？**

A: 正常现象，说明接口存在但需要先登录获取 token。

**Q: 代理目标要改成其他地址怎么办？**

A: 在 `frontend/.env` 中设置：

```env
VITE_API_PROXY_TARGET=http://127.0.0.1:9090
```

## 本地质量检查

```powershell
cd D:\XinRagent\frontend
npm run typecheck
npm run lint
npm run build
```

后端测试：

```powershell
cd D:\XinRagent\python-backend
python -m pytest
```
