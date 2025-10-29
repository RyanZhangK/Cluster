# 数据库交互规范

## 数据库设计

1. **表设计原则**
   - 每个表必须有主键
   - 使用下划线命名法 (如 `node_status`)
   - 避免使用保留字作为列名
   - 添加必要的索引
   - 为每个表添加创建时间戳字段

2. **数据库类型**
   - `NODE_STATUS`: 节点状态数据
   - `GAME_CONFIG`: 游戏配置数据

3. **初始化脚本**
   - 放在模块的`__init__`方法中
   - 包含表创建和初始数据插入

## 查询规范

1. **SQL编写**
   - 使用参数化查询防止SQL注入
   - 复杂查询添加注释说明
   - 避免使用`SELECT *`，明确指定列名

2. **异步操作**
   - 查询使用`query()`方法
   - 写入使用`write()`方法
   - 通过回调函数处理结果

示例：
```python
# 查询示例
db_manager.query(
    DatabaseType.NODE_STATUS,
    "SELECT node_id, status FROM node_status WHERE last_update > ?",
    (timestamp,),
    callback=handle_result
)

# 写入示例
db_manager.write(
    DatabaseType.GAME_CONFIG,
    "UPDATE game_settings SET value = ? WHERE key = ?",
    (new_value, key),
    callback=handle_result
)
```

## 事务管理

1. **自动提交**
   - 默认每个语句自动提交
   - 需要事务时使用`BEGIN TRANSACTION`和`COMMIT`

2. **批量操作**
   - 使用`executemany()`提高性能
   - 大批量操作分批处理

## 连接管理

1. **连接池**
   - 每个工作线程维护独立连接
   - 连接数根据负载动态调整
   - 空闲连接超时关闭

2. **线程安全**
   - 禁止跨线程共享连接
   - 使用队列传递数据库操作

## 错误处理

1. **统一响应格式**
   - 成功响应：
     ```json
     {
       "success": true,
       "data": [...],
       "timestamp": 1234567890
     }
     ```
   - 错误响应：
     ```json
     {
       "success": false,
       "error": "错误描述",
       "timestamp": 1234567890
     }
     ```

2. **错误分类**
   - 连接错误：立即重试或告警
   - 语法错误：记录并修复代码
   - 约束错误：检查业务逻辑

## 性能优化

1. **索引策略**
   - 查询条件列添加索引
   - 避免过度索引

2. **查询优化**
   - 使用EXPLAIN分析慢查询
   - 避免全表扫描

## 备份与恢复

1. **定期备份**
   - 每日全量备份
   - 备份文件加密存储

2. **恢复流程**
   - 验证备份完整性
   - 关闭服务后恢复
   - 恢复后完整性检查
