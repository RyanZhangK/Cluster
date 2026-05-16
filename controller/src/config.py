import logging
import tomllib
from asyncio import Event
from pathlib import Path as _Path

# MQTT 配置
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_QOS = 1
MQTT_TOPIC_SUB = "node/status"
MQTT_TOPIC_PUB = "node/{node_id}/status"

# 内嵌 Broker 配置
# 业务环境同样启用，外部访问通过 frp 反代实现
EMBEDDED_BROKER = True
BROKER_BIND_HOST = "0.0.0.0"  # 监听所有网卡，便于 frp 反代和局域网访问
BROKER_BIND_PORT = 1883

# 心跳与看门狗
HEARTBEAT_TIMEOUT = 600  # 秒，节点心跳超时时间
WATCHDOG_INTERVAL = 30  # 秒，看门狗检查间隔

# 消息格式
MSG_LENGTH = 7
NODE_ID_LENGTH = 5

BROKER_READY = Event()

# 路径：已安装时用系统路径，开发环境用相对路径
_INSTALLED_AUDIO = _Path("/usr/local/share/cluster/audio")
if _INSTALLED_AUDIO.exists():
    AUDIO_DIR = str(_INSTALLED_AUDIO)
    # 已安装：日志写到用户家目录
    LOG_DIR = str(_Path.home() / ".local" / "share" / "cluster" / "log")
else:
    AUDIO_DIR = str(_Path(__file__).parent / "resources" / "audio")
    # 开发环境：日志写到相对路径
    LOG_DIR = "log"

# 音频文件映射
AUDIO_FILES = {
    # 系统上下线语音播报
    "sys_online": "SYS_ONLINE.wav",
    "sys_offline": "SYS_OFFLINE.wav",
    # 游戏事件
    "game_started": "GAME_START.wav",
    "game_stopped": "GAME_STOP.wav",
    # 节点激活提示（每个队伍不同音效）
    "activated_A": "TEAM_A_READY.wav",
    "activated_B": "TEAM_B_READY.wav",
    "activated_C": "TEAM_C_READY.wav",
    "activated_D": "TEAM_D_READY.wav",
    # 队伍淘汰（队伍特定）
    "eliminated_A": "TEAM_A_ELI.wav",
    "eliminated_B": "TEAM_B_ELI.wav",
    "eliminated_C": "TEAM_C_ELI.wav",
    "eliminated_D": "TEAM_D_ELI.wav",
    # 队伍胜利（队伍特定）
    "victory_A": "TEAM_A_WIN.wav",
    "victory_B": "TEAM_B_WIN.wav",
    "victory_C": "TEAM_C_WIN.wav",
    "victory_D": "TEAM_D_WIN.wav",
    # 爆破模式胜利
    "victory_T": "TEAM_T_WIN.wav",
    "victory_CT": "TEAM_CT_WIN.wav",
    # 炸弹事件
    "bomb_activated": "BOOM_PLANTED.wav",
    "bomb_defused": "BOOM_DEFUSED.wav",
}

_LOCAL_CONFIG_PATH = _Path(__file__).parent.parent.parent / "config.toml"
logger = logging.getLogger(__name__)

if _LOCAL_CONFIG_PATH.exists() and tomllib:
    try:
        with open(_LOCAL_CONFIG_PATH, "rb") as f:
            _local_data = tomllib.load(f)
        _current_globals = globals()
        for _key, _value in _local_data.items():
            if _key in _current_globals and _key.isupper():
                if isinstance(_current_globals[_key], dict) and isinstance(
                    _value, dict
                ):
                    _current_globals[_key].update(_value)
                else:
                    _current_globals[_key] = _value
    except Exception as e:
        logger.warning(f"config.toml解析失败: {e}")
