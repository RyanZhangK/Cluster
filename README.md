# Cluster

[![Python版本](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.9.0-green.svg)](https://doc.qt.io/qtforpython/)
[![MQTT](https://img.shields.io/badge/MQTT-3.1.1-orange.svg)](http://mqtt.org/)
[![License: WTFPL](https://img.shields.io/badge/License-WTFPL-yellow.svg)](./LICENSE)

> 真人CS / 激光对抗游戏控制系统 - 支持多队伍实时对抗、语音播报与桌面管理

## 简介

Cluster 是一套专为真人CS、激光对抗等多人对抗游戏设计的控制系统。系统通过 MQTT 无线通信连接分布式节点，实现对玩家状态（存活/淘汰）的实时监控，配合语音播报（TTS）进行游戏流程提示，并通过桌面管理端进行配置与监控。

### 适用场景

- 真人CS俱乐部对抗赛
- 激光对抗/War Game
- 室内/室外团队竞技活动
- 研学营地的团队对抗游戏

---

## 系统架构

### 核心组件

| 模块 | 文件 | 技术栈 | 功能说明 |
|------|------|--------|----------|
| 主控模块 | [main.py](controller/main.py) | Python 3.13+ | 进程管理、自动重启、日志轮转 |
| 数据库 | [database_process.py](controller/database_process.py) | SQLite3 | 节点状态、游戏配置存储 |
| MQTT通信 | [mqtt_process.py](controller/mqtt_process.py) | paho-mqtt | 节点心跳、激活消息处理 |
| 游戏逻辑 | [game_process.py](controller/game_process.py) | Python + edge-tts | 征服模式、胜负判定、TTS语音播报 |
| 桌面端 | [desktop_app.py](controller/desktop_app.py) | PySide6 | 节点监控、配置编辑、日志浏览 |
| Web端 | [flask_app.py](controller/flask_app.py) | Flask | RESTful API（可选） |
| 日志工具 | [logging_utils.py](controller/logging_utils.py) | logging | 模块化日志配置 |

### 节点类型

```
STA01 ~ STA04  : 普通节点（每队一个，代表玩家队伍）
DET01 ~ DET06  : 检测节点（用于检测激活器信号）
```

### MQTT 消息协议

消息格式为 7 字节 ASCII 字符串：

```
{node_id}{action_type}{extra_info}
```

| 消息类型 | 格式示例 | 说明 |
|----------|----------|------|
| 心跳包 | `STA01H0` | 节点存活心跳（类型=H，额外=0） |
| 激活包 | `STA01A1` | 激活状态上报（类型=A，额外=1~4） |

- **node_id**: 5字符节点ID（如 `STA01`、`DET03`）
- **action_type**: 动作类型（H=心跳/A=激活）
- **extra_info**: 附加信息（心跳时固定为0，激活时为1-4）

---

## 目录结构

```
Cluster/
├── controller/                    # 主控端 Python 代码
│   ├── main.py                   # 进程管理入口
│   ├── database_process.py        # SQLite 数据库管理
│   ├── mqtt_process.py           # MQTT 消息处理
│   ├── game_process.py          # 游戏逻辑 + TTS 语音
│   ├── desktop_app.py           # PySide6 桌面管理端
│   ├── flask_app.py             # Flask Web API
│   ├── logging_utils.py         # 日志工具
│   ├── log/                     # 运行日志目录
│   └── resource/                 # 静态资源
│       ├── *.db                 # SQLite 数据库文件
│       ├── tts_temp/            # TTS 临时音频
│       ├── static/              # Web 静态文件
│       └── templates/           # Web 模板
├── node_a/                       # ESP8266 节点固件
│   ├── ESP8266/                  # 基础节点固件
│   └── ESP8266_B/                # 带矩阵键盘节点
├── MQTTbroker/                    # MQTT Broker 启动脚本
│   ├── mqttbroker.sh
│   ├── mqttbroker-ubuntu.sh
│   └── mqttbroker-arch.sh
└── README.md
```

---

## 功能特性

- **节点实时监控** - 通过 MQTT 监控所有 STA/DET 节点在线状态
- **MQTT 双向通信** - 心跳保活 + 激活状态上报
- **征服模式** - 支持 2-4 队对抗，自动判定胜负
- **TTS 语音播报** - Edge TTS 实时语音提示（队伍就绪、对局开始、淘汰、胜利）
- **桌面管理端** - PySide6 GUI，节点状态监控、游戏配置编辑、日志浏览
- **进程自动管理** - 主控模块自动启动、子进程异常退出自动重启
- **日志轮转** - 按日期/大小自动轮转，防止日志无限增长

---

## 快速开始

### 环境要求

- Python 3.13+
- MQTT Broker (推荐 Mosquitto)
- ffplay (用于 TTS 播放，需安装 ffmpeg)

### 1. 克隆仓库

```bash
git clone https://github.com/chijumaodejiyu/Cluster.git
cd Cluster
```

### 2. 安装依赖

```bash
pip install paho-mqtt PySide6 Flask edge-tts psutil
```

### 3. 配置 MQTT Broker

使用项目提供的脚本启动 Mosquitto：

```bash
# Linux (Ubuntu/Debian)
bash MQTTbroker/mqttbroker-ubuntu.sh

# Linux (Arch)
bash MQTTbroker/mqttbroker-arch.sh
```

或手动启动：

```bash
mosquitto -p 1883
```

### 4. 启动主程序

```bash
cd controller
python main.py
```

启动顺序：
1. 数据库模块 → 2. MQTT模块 → 3. 桌面端 → 4. 游戏逻辑模块

### 5. 配置节点

在数据库中初始化节点：

```python
# 启动后自动创建以下节点：
# STA01, STA02, STA03, STA04  (状态节点)
# DET01, DET02, DET03, DET04, DET05, DET06  (检测节点)
```

---

## 使用说明

### 桌面管理端

启动后显示主窗口，包含三个面板：

#### 节点状态面板（左上）

- **STA节点**: 显示队伍在线/激活状态
- **DET节点**: 显示检测器状态
- 自动刷新间隔：5秒

#### 游戏配置面板（右上）

- **队伍数量**: 2-4 队
- **游戏模式**: conquer（征服模式）
- 点击「保存配置」生效

#### 系统日志面板（下方）

- 查看各模块运行日志
- 支持刷新、清空操作

### 游戏流程

```
1. 玩家刷卡激活 → 节点发送激活包 (STA01A1)
2. 系统检测到满足开赛条件 (如 2队以上就绪)
3. 发送 TTS 语音 "对局开始"
4. 游戏进行中，监控各队状态
5. 某队被淘汰 → 语音播报 "X队被淘汰"
6. 剩余一队 → 语音播报 "X队取得胜利"
7. 游戏结束，重置状态
```

### MQTT 主题

| 主题 | 方向 | 说明 |
|------|------|------|
| `node/status` | ← 节点 | 订阅所有节点状态消息 |
| `node/{node_id}/status` | → 节点 | 发布节点状态更新 |

---

## 配置说明

### MQTT 配置

编辑 [mqtt_process.py](controller/mqtt_process.py)：

```python
MQTT_BROKER = "127.0.0.1"   # Broker 地址
MQTT_PORT = 1883              # 端口
HEARTBEAT_TIMEOUT = 600       # 心跳超时时间（秒）
```

### 数据库路径

编辑 [database_process.py](controller/database_process.py)：

```python
DB_PATHS = {
    DatabaseType.NODE_STATUS: Path("resource/node_status.db"),
    DatabaseType.GAME_CONFIG: Path("resource/game_config.db")
}
```

### 游戏配置

游戏配置存储在 `resource/game_config.db`：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| id | INTEGER | 1 | 主键（固定为1） |
| team_count | INTEGER | 2 | 队伍数量 |
| game_mode | TEXT | conquer | 游戏模式 |
| game_state | TEXT | unstart | 游戏状态 |

---

## API 参考

### Flask Web API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 返回前端页面 |
| `/api/status` | GET | 获取所有节点状态 |
| `/api/config` | GET/POST | 获取/更新游戏配置 |
| `/api/logs` | GET | 获取日志列表 |

#### 响应格式

```json
{
  "success": true,
  "data": { ... },
  "timestamp": "2024-01-01T12:00:00"
}
```

---

## 开发指南

### 模块启动顺序

在 [main.py](controller/main.py) 中定义：

```python
MODULES = [
    "database_process.py",  # 数据库读写模块
    "mqtt_process.py",       # MQTT 信息处理模块
    "desktop_app.py",        # 桌面管理端应用
    "game_process.py"       # 游戏逻辑管理和音频生成播放模块
]
```

### 添加新模块

1. 在 `MODULES` 列表中添加模块文件名
2. 实现标准的日志配置（参考 `logging_utils.py`）
3. 实现进程存活监控兼容

### 日志规范

- 使用 `configure_module_logging()` 创建模块日志
- 日志文件位于 `controller/log/` 目录
- 格式：`{module}_{timestamp}.log`
- 自动清理 7 天前日志

---

## 常见问题

### Q: TTS 播放失败

A: 确保安装 ffmpeg 并配置在 PATH 中：

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

### Q: MQTT 连接失败

A: 检查 Mosquitto 是否运行：

```bash
ps aux | grep mosquitto
# 或重新启动
mosquitto -d
```

### Q: 节点显示离线

A: 检查节点与控制器的网络连通性，确认 MQTT Broker 地址正确。

### Q: 桌面端无法启动

A: 确保显示器环境正确（Linux 下可能需要配置 X11）：

```bash
export QT_QPA_PLATFORM=linuxfb
# 或
export QT_QPA_PLATFORM=xcb
```

---

## 许可证

本项目基于 WTFPL（Do What The F*ck You Want To Public License）许可证开源，详见 [LICENSE](./LICENSE) 文件。

---

## 鸣谢

- [paho-mqtt](https://www.eclipse.org/paho/) - MQTT 客户端库
- [PySide6](https://doc.qt.io/qtforpython/) - Qt for Python
- [Edge TTS](https://github.com/rany2/edge-tts) - 微软 Edge TTS Python 绑定
- Qt Company - Qt 框架

---

## 联系

如有问题或建议，请提交 Issue 或 Pull Request。

项目主页：https://github.com/chijumaodejiyu/Cluster