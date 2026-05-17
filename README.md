# Cluster — MQTT 节点管理与游戏控制系统

一个基于 MQTT 的嵌入式节点管理系统，支持三种游戏模式（征服/占领/爆破），集成实时监控、音效播报、游戏状态管理。

## 系统架构

```mermaid
%%{init: {'theme': 'dark'}}%%
graph TD
    %% 去掉你原来的 classDef，或者改成深色系
    subgraph Controller ["Controller (主控)"]
        MQTT_B["MQTT Broker<br>(amqtt)"]
        Node_M["Node Manager<br>(内存缓存)"]
        Game_M["Game Manager<br>(状态机)"]
        
        EventBus{{"EventBus (信号总线)"}}
        
        UI["UI<br>(PySide6)"]
        Audio["Audio<br>Player"]
        MQTT_C["MQTT<br>Client"]
        
        MQTT_B & Node_M & Game_M <--> EventBus
        EventBus <--> UI & Audio & MQTT_C
    end

    subgraph ESP ["ESP8266 节点网络 (MQTT)"]
        direction LR

        STA01["STA01"]
        STA02["STA02"]
        DET01["DET01"]
        More["..."]

        STA01 --- STA02 --- DET01 --- More
    end

    UI --> ESP
    MQTT_C --> ESP
```

## 功能特性

### 节点监控
- **动态发现**：节点首次发送心跳时自动创建
- **实时状态**：在线/离线、激活队伍、最后心跳时间
- **心跳看门狗**：600 秒超时自动标记离线
- **统计面板**：总节点数、在线数、离线数

### 游戏模式

#### 1. 征服模式 (Conquest)
- **开始条件**：激活的 STA 节点数 == 预设队伍数
- **淘汰机制**：STA 节点再次激活 → 对应队伍淘汰
- **胜利条件**：剩余队伍数 == 1

#### 2. 占领模式 (Occupy)
- **开始条件**：激活的 STA 节点数 == 预设队伍数
- **计分机制**：统计各队伍激活的 DET 节点数
- **胜利条件**：某队伍激活的 DET 节点数 > 在线 DET 总数 / 2

#### 3. 爆破模式 (Bomb)
- **开始条件**：两个 STA 节点激活（装弹方/拆弹方）
- **炸弹激活**：装弹方激活指定 DET 节点 → 40 秒倒计时
- **胜利条件**：
  - T 队：倒计时读完
  - CT 队：任何时刻激活炸弹节点拆除

### 音效系统
- **串行播放队列**：同一时刻只播放一条，避免混音
- **延迟加载**：首次播放时才初始化 QSoundEffect，避免启动阻塞
- **队伍特定音效**：激活/淘汰/胜利各有队伍专属音效
- **紧急手动模式**：可中断队列、立即播放任意音效

### UI 设计
- **深蓝管理风格**：专业后端管理界面配色
- **多页面分层**：节点监控 / 游戏控制 / 游戏状态 / 紧急手动
- **实时反馈**：游戏状态横幅、队伍卡片、倒计时进度条
- **响应式布局**：自适应窗口大小

## 快速开始

### 环境要求
Python 3.12+

### 运行
```bash
make dev # uv run controller
```

### 测试消息
```bash
uv run controller/test/send_test_message.py
```

### Pre-Commit安装
```bash
uv sync
uv run pre-commit install
```

## 消息格式

MQTT 消息格式：7 字节 ASCII

```
[节点ID(5)] [动作(1)] [参数(1)]
  STA01      H        0    # STA01 心跳
  DET01      A        2    # DET01 激活为队伍 B (1=A, 2=B, 3=C, 4=D)
```

- **动作类型**：
  - `H`：心跳（参数必须为 `0`）
  - `A`：激活（参数为队伍编号 1-4 或 A-D）

## 项目结构

```
Cluster/
├── controller/
│   ├── log/                        # 日志输出目录
│   ├── src/
│   │   ├── main.py                 # 应用入口
│   │   ├── UI.py                   # PySide6 UI 界面
│   │   ├── node_manager.py         # 节点状态管理
│   │   ├── game_manager.py         # 游戏状态机
│   │   ├── mqtt_client.py          # MQTT 客户端
│   │   ├── embedded_broker.py      # 内嵌 MQTT Broker
│   │   ├── audio_player.py         # 音效播放队列
│   │   ├── event_bus.py            # 信号总线
│   │   ├── config.py               # Controller配置
│   │   ├── resources/
│   │       └── audio/              # 音效文件目录
│   ├── test/
│       └── send_test_message.py    # MQTT 测试脚本
├── mcu/                            # ESP8266 固件代码
├── README.md                       # 本文件
├── LICENSE                         # 开源协议
```

## 配置说明

编辑 `config.toml` （支持.env和系统环境变量）：

```python
# MQTT 配置
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC_SUB = "node/status"

# 内嵌 Broker 配置
EMBEDDED_BROKER = True
BROKER_BIND_HOST = "0.0.0.0"
BROKER_BIND_PORT = 1883

# 心跳与看门狗
HEARTBEAT_TIMEOUT = 600  # 秒
WATCHDOG_INTERVAL = 30   # 秒
```

## 日志

日志文件位于 `controller/log/controller.log.*`，按天滚动保留 7 天。

## 开发指南

### 添加新的游戏模式

1. 在 `game_manager.py` 的 `GameMode` 枚举中添加新模式
2. 在 `GameManager.on_sta_activated()` 和 `on_det_activated()` 中实现逻辑
3. 在 `UI.py` 的游戏控制页添加对应的 UI 控件

### 添加新的音效

1. 将音效文件放入 `controller/resources/audio/`
2. 在 `config.py` 的 `AUDIO_FILES` 中添加映射
3. 在 `audio_player.py` 中添加对应的 `play_*()` 方法

## 许可证

本项目采用 **CC BY-NC-SA 4.0** 协议（署名-非商业性使用-相同方式共享）。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request。

## 联系方式

- 项目维护者：RyanZ
- 邮箱：[ryanzzzz@foxmail.com]

