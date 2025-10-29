# API开发规范

## 基础原则

1. 遵循 **RESTful** 设计风格
2. 使用 **JSON** 作为数据交换格式
3. 所有API端点以 `/api/` 开头
4. 版本控制通过请求头 `Accept: application/vnd.api.v1+json` 实现

## 路由命名

- 资源名使用 **复数形式** (如`/api/nodes`)
- 避免动词出现在URL中(使用HTTP方法区分操作)
- 嵌套资源使用路径表示关系 (如`/api/nodes/1/sensors`)

## 请求规范

### HTTP方法使用

- `GET` - 获取资源
- `POST` - 创建资源
- `PUT` - 全量更新资源
- `PATCH` - 部分更新资源
- `DELETE` - 删除资源

### 请求头

必须包含：
```http
Content-Type: application/json
Accept: application/json
```

### 请求参数

- 查询参数：用于过滤、排序、分页
  ```http
  GET /api/nodes?status=active&sort=-created_at&page=2
  ```
- 路径参数：标识特定资源
  ```http
  GET /api/nodes/123
  ```
- Body参数：创建/更新时使用
  ```json
  {
    "name": "Node 1",
    "status": "active"
  }
  ```

## 响应规范

### 成功响应

- 包含`data`字段
- 分页资源包含`meta`字段

示例：
```json
{
  "data": [...],
  "meta": {
    "total": 100,
    "page": 2,
    "per_page": 20
  }
}
```

### 错误响应

统一格式：
```json
{
  "error": {
    "code": "invalid_request",
    "message": "缺少必要参数: name",
    "details": {
      "param": "name"
    }
  }
}
```

### 状态码

- `200 OK` - 成功GET请求
- `201 Created` - 成功创建资源
- `204 No Content` - 成功删除/无内容返回
- `400 Bad Request` - 请求参数错误
- `401 Unauthorized` - 未认证
- `403 Forbidden` - 无权限
- `404 Not Found` - 资源不存在
- `500 Internal Server Error` - 服务器错误

## 认证授权

1. 使用Bearer Token认证：
   ```http
   Authorization: Bearer <token>
   ```
2. Token通过登录接口获取
3. 敏感操作需额外权限验证

## 文档要求

1. 每个路由必须有文档字符串：
   ```python
   @app.route('/api/nodes')
   def get_nodes():
       """
       获取节点列表
       
       Query Params:
         status (str): 过滤节点状态(active/inactive)
         page (int): 页码(默认1)
         per_page (int): 每页数量(默认20)
       
       Returns:
         包含节点列表和分页信息的JSON响应
       """
   ```
2. 使用Swagger/OpenAPI生成API文档

## 日志记录

1. 记录所有API请求：
   ```python
   logger.info(f"API请求: {request.method} {request.path}")
   ```
2. 错误请求记录完整堆栈
3. 敏感信息需脱敏
