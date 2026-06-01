# 前端接口盘点

本文档按 `frontend/src/services` 记录原版前端当前依赖的后端接口，用作 Python 后端 10 天改造的接口待办清单。路径默认带有前缀 `/api/ragent`，开发环境由 Vite 代理转发到 Python 后端。

## 第 1 批：登录与用户

| 服务文件 | 方法 | 接口 | 状态 |
| --- | --- | --- | --- |
| `authService.ts` | `POST` | `/auth/login` | 已对齐 |
| `authService.ts` | `POST` | `/auth/logout` | 已对齐 |
| `authService.ts` | `GET` | `/user/me` | 已对齐 |
| `userService.ts` | `GET` | `/users` | 已对齐 |
| `userService.ts` | `POST` | `/users` | 已对齐 |
| `userService.ts` | `PUT` | `/users/{id}` | 已对齐 |
| `userService.ts` | `DELETE` | `/users/{id}` | 已对齐 |
| `userService.ts` | `PUT` | `/user/password` | 已对齐 |

## 第 2 批：会话与聊天

| 服务文件 | 方法 | 接口 | 状态 |
| --- | --- | --- | --- |
| `sessionService.ts` | `GET` | `/conversations` | 待对齐 |
| `sessionService.ts` | `PUT` | `/conversations/{conversationId}` | 待对齐 |
| `sessionService.ts` | `DELETE` | `/conversations/{conversationId}` | 待对齐 |
| `sessionService.ts` | `GET` | `/conversations/{conversationId}/messages` | 待对齐 |
| `chatService.ts` | `POST` | `/rag/v3/stop` | 待对齐 |
| `chatStore.ts` | `GET` | `/rag/v3/chat` | 待对齐 |

## 第 3 批：知识库、文档与分块

| 服务文件 | 接口范围 | 状态 |
| --- | --- | --- |
| `knowledgeService.ts` | 知识库、文档、分块 CRUD | 待对齐 |
| `ingestionService.ts` | 入库任务、Pipeline、节点状态 | 待对齐 |

## 第 4 批：后台管理

| 服务文件 | 接口范围 | 状态 |
| --- | --- | --- |
| `dashboardService.ts` | 后台概览、性能、趋势 | 待对齐 |
| `ragTraceService.ts` | Trace run、Trace detail、Trace node | 待对齐 |
| `sampleQuestionService.ts` | 样例问题 CRUD | 待对齐 |
| `intentTreeService.ts` | 意图树 CRUD 与批量操作 | 待对齐 |
| `queryTermMappingService.ts` | 查询词映射 CRUD | 待对齐 |
| `settingsService.ts` | RAG 系统设置 | 待对齐 |

## 对齐原则

- 优先保持前端服务层不改，Python 后端兼容 Java 版接口路径和字段。
- 统一响应保持 `{ code, message, data }`，成功码固定为字符串 `"0"`。
- 前端 token 会直接写入 `Authorization` 请求头，后端同时兼容裸 token 与 `Bearer token`。
- 每完成一个页面，补对应接口测试，避免后续字段兼容回退。
