# 前端接口契约

本文档记录从原版 `D:\Ragent\frontend` 接入 Python 后端时，前端首批依赖的接口契约。Python 后端统一挂载在 `/api/ragent` 下，前端开发环境通过 Vite 代理转发到 `http://localhost:9090`。

## 统一响应

前端 `src/services/api.ts` 只认以下响应结构：

```json
{
  "code": "0",
  "message": "success",
  "data": {}
}
```

`code` 不等于 `"0"` 时，前端会把 `message` 作为错误提示。

## 认证接口

### POST `/api/ragent/auth/login`

请求：

```json
{
  "username": "admin",
  "password": "admin"
}
```

响应 `data`：

```json
{
  "userId": "2001523723396308993",
  "username": "admin",
  "role": "admin",
  "avatar": "https://example.com/avatar.png",
  "token": "access-token",
  "access_token": "access-token",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

说明：`token` 给前端直接使用，`access_token` 保留给后端已有测试和兼容调用。

### POST `/api/ragent/auth/logout`

请求头：

```text
Authorization: <token>
```

兼容：

```text
Authorization: Bearer <token>
```

响应 `data` 为 `null`。

### GET `/api/ragent/user/me`

请求头同上。

响应 `data`：

```json
{
  "id": "2001523723396308993",
  "userId": "2001523723396308993",
  "username": "admin",
  "role": "admin",
  "avatar": "https://example.com/avatar.png"
}
```

## 用户管理接口

### GET `/api/ragent/users`

查询参数：

- `current`：当前页，默认 `1`
- `size`：每页数量，默认 `10`
- `keyword`：用户名关键字，可选

响应 `data`：

```json
{
  "records": [
    {
      "id": "2001523723396308993",
      "username": "admin",
      "role": "admin",
      "avatar": "https://example.com/avatar.png",
      "createTime": "2026-05-31T10:00:00",
      "updateTime": "2026-05-31T10:00:00"
    }
  ],
  "total": 1,
  "size": 10,
  "current": 1,
  "pages": 1
}
```

### POST `/api/ragent/users`

请求：

```json
{
  "username": "new-user",
  "password": "secret",
  "role": "user",
  "avatar": null
}
```

响应 `data` 为新用户 ID。

### PUT `/api/ragent/users/{id}`

请求字段均可选：

```json
{
  "username": "new-name",
  "password": "new-secret",
  "role": "admin",
  "avatar": null
}
```

响应 `data` 为 `null`。

### DELETE `/api/ragent/users/{id}`

逻辑删除用户，响应 `data` 为 `null`。

### PUT `/api/ragent/user/password`

请求：

```json
{
  "currentPassword": "old-secret",
  "newPassword": "new-secret"
}
```

响应 `data` 为 `null`。
