# MQTT通讯协议规范

## 概述

本项目采用MQTT协议进行节点与控制器之间的通讯，使用**7字节ASCII文本格式**传输简洁高效的指令。

## 连接配置

| 配置项 | 值 |
|--------|-----|
| Broker地址 | 127.0.0.1 |
| 端口 | 1883 |
| 订阅主题 | node/status |
| 发布主题 | node/{node_id}/status |
| QoS级别 | 1 |

## 消息格式

### 统一格式（7字节）

```
{node_id}{action_type}{extra_info}
```

| 字段 | 长度 | 说明 |
|------|------|------|
| node_id | 5字符 | 节点标识符 |
| action_type | 1字符 | 动作类型（H心跳/A激活） |
| extra_info | 1字符 | 附加信息 |

---

## 节点ID定义

### STA系列 - 队伍节点（4个）

| 节点ID | 说明 |
|--------|------|
| STA01 | 队伍1节点 |
| STA02 | 队伍2节点 |
| STA03 | 队伍3节点 |
| STA04 | 队伍4节点 |

### DET系列 - 探测器节点（6个）

| 节点ID | 说明 |
|--------|------|
| DET01 | 探测器1 |
| DET02 | 探测器2 |
| DET03 | 探测器3 |
| DET04 | 探测器4 |
| DET05 | 探测器5 |
| DET06 | 探测器6 |

---

## 消息类型详解

### 1. 心跳消息（Heartbeat）

**格式**: `{NODE_ID}H0`

**示例**:
- `STA01H0` - STA01节点心跳
- `DET01H0` - DET01节点心跳

**处理逻辑**:
1. 解析心跳包，重置该节点的计时器
2. 更新数据库 `online_status = 1`
3. 发布节点状态到 `node/{node_id}/status`

**心跳超时**: 600秒（10分钟）

### 2. 激活消息（Activation）

**格式**: `{NODE_ID}A{TEAM_NUM}`

| 节点ID | TEAM_NUM | 含义 |
|--------|----------|------|
| STA01 | A1-A4 | 第1-4队激活 |
| STA02 | A1-A4 | 第1-4队激活 |
| ... | ... | ... |

**示例**:
- `STA01A1` - STA01被队伍1激活
- `STA02A3` - STA02被队伍3激活

**extra_info有效值**: `1`, `2`, `3`, `4`（队伍编号）

**处理逻辑**:
1. 更新数据库 `active_status = TEAM_NUM`, `activator = STAxx`
2. 若满足游戏开始条件（已激活队伍数 >= 配置队伍数），触发游戏开始

---

## 完整通讯流程

```
[节点硬件] ──MQTT──> [mqtt_process]
                            │
                            ├── 解析消息（_parse_message）
                            │      ├── 验证长度（必须7字节）
                            │      ├── 验证node_id（必须在NODE_IDS列表中）
                            │      └── 验证action_type和extra_info
                            │
                            ├── 处理动作
                            │      ├── H: 更新在线状态，重置计时器
                            │      └── A: 更新激活状态
                            │
                            └── 写入数据库（database_process）
                                   │
                                   └── 状态发布到 node/{node_id}/status
```

---

## 数据库存储

### node_status.db - node_status表

| 字段 | 类型 | 说明 |
|------|------|------|
| node_id | TEXT PRIMARY KEY | 节点ID |
| online_status | INTEGER | 在线状态（0/1） |
| active_status | INTEGER | 激活状态（0未激活，1-4队伍编号） |
| activator | TEXT | 激活者ID |
| last_update | TIMESTAMP | 最后更新时间 |

---

## 消息解析验证规则

```python
# 长度验证
if len(raw_msg) != 7:
    raise ValueError("无效消息长度")

# node_id验证（必须在NODE_IDS列表中）
if node_id not in NODE_IDS:
    raise ValueError("无效节点ID")

# action_type验证
if action_type not in ('H', 'A'):
    raise ValueError("无效动作类型")

# 心跳包extra_info必须为0
if action_type == 'H' and extra_info != '0':
    raise ValueError("心跳包补充信息必须为0")

# 激活包extra_info必须为1-4
if action_type == 'A' and extra_info not in ('1', '2', '3', '4'):
    raise ValueError("激活包补充信息必须为1-4")
```

---

## MQTT模块心跳超时机制

```python
HEARTBEAT_TIMEOUT = 600  # 10分钟

class NodeTimerManager:
    def reset_timer(node_id):
        # 重置节点计时器

    def check_timeouts():
        # 检查所有计时器
        # 若超时：更新数据库 online_status = False
        # 删除计时器记录
```

---

## 示例消息序列

### 游戏开始流程

```
1. 节点发送: STA01A1  (队伍1就绪)
2. 节点发送: STA02A2  (队伍2就绪)
3. 系统检测: 已激活2队 >= 配置队伍数(2)
4. 系统触发: game_state = 'started'
5. 系统播放TTS: "对局开始"
```

### 节点掉线流程

```
1. 节点最后心跳时间: T
2. 600秒后计时器超时
3. 系统更新: online_status = 0
4. 系统日志: "节点 xxx 心跳超时"
```

---

## 主题说明

| 方向 | 主题 | Payload格式 | 说明 |
|------|------|-------------|------|
| 订阅 | node/status | `STA01H0` (7字节) | 接收节点消息 |
| 发布 | node/{node_id}/status | JSON | 发布节点状态 |

### 状态发布JSON格式

```json
{
    "node_id": "STA01",
    "online": true,
    "active": true,
    "timestamp": "2024-01-01 12:00:00",
    "source": "db_update"
}
```
