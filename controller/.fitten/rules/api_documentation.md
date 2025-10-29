# API 文档规范

## 系统状态接口
### GET /api/system_stats
**响应格式:**
```json
{
  "network": {
    "status": "string (connected/disconnected)",
    "dBm": "number"
  },
  "cpu_usage": "number (0-100)",
  "memory_usage": "number (0-100)"
}
```

## 节点状态接口
### GET /api/node_status
**响应格式:**
```json
[
  {
    "node_id": "string",
    "online_status": "number (0/1)",
    "active_status": "string",
    "last_update": "string (timestamp)"
  }
]
```

## 游戏配置接口
### GET /api/game_config
**响应格式:**
```json
{
  "id": "number",
  "team_count": "number",
  "game_mode": "string",
  "game_state": "string",
  "timestamp": "string"
}
```

### POST /api/update_config
**请求格式:**
```json
{
  "team_count": "number",
  "game_mode": "string",
  "game_state": "string"
}
```

**响应格式:**
```json
{
  "success": "boolean",
  "error": "string (optional)"
}
```

## 日志接口
### GET /api/log_files
**响应格式:**
```json
["filename1.log", "filename2.log"]
```

### GET /api/log_content?file={filename}
**响应格式:**
```text
纯文本日志内容
```

## 数据格式说明
1. 所有时间戳格式: ISO 8601
2. 数字字段必须为有效数值
3. 字符串字段必须为非空
4. 错误响应包含详细错误信息
