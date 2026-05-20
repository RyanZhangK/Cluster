import logging
from asyncio import Event
from pathlib import Path as _Path

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)


class MQTTSettings(BaseSettings):
    """MQTT 配置"""

    broker: str = "127.0.0.1"
    port: int = 1883
    qos: int = 1
    topic_sub: str = "node/status"
    topic_pub: str = "node/{node_id}/status"


class BrokerSettings(BaseSettings):
    """内嵌 Broker 配置"""

    # 业务环境同样启用，外部访问通过 frp 反代实现
    enabled: bool = True
    bind_host: str = "0.0.0.0"  # 监听所有网卡，便于 frp 反代和局域网访问
    bind_port: int = 1883


class GameSettings(BaseSettings):
    """心跳与看门狗"""

    heartbeat_timeout: int = 600  # 秒，节点心跳超时时间
    watchdog_interval: int = 30  # 秒，看门狗检查间隔
    ui_hot_reload: bool = True


class MessageSettings(BaseSettings):
    """消息格式"""

    msg_length: int = 7
    node_id_length: int = 5


class FrpcSettings(BaseSettings):
    """frpc 内网穿透客户端配置"""

    server_addr: str = ""
    server_port: int = 7000
    auth_token: str = ""
    proxies: str = "[]"


class Settings(BaseSettings):
    """Cluster 主配置类"""

    mqtt: MQTTSettings = Field(default_factory=MQTTSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    game: GameSettings = Field(default_factory=GameSettings)
    message: MessageSettings = Field(default_factory=MessageSettings)
    frpc: FrpcSettings = Field(default_factory=FrpcSettings)

    model_config = SettingsConfigDict(
        env_prefix="CLUSTER_",
        env_nested_delimiter="__",
        extra="ignore",
        toml_file="config.toml",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        from pydantic_settings import TomlConfigSettingsSource

        return (
            init_settings,  # 默认值
            TomlConfigSettingsSource(settings_cls),  # config.toml
            dotenv_settings,  # .env
            env_settings,  # 系统环境变量
            file_secret_settings,
        )


settings = Settings()

# MQTT 配置
MQTT_BROKER = settings.mqtt.broker
MQTT_PORT = settings.mqtt.port
MQTT_QOS = settings.mqtt.qos
MQTT_TOPIC_SUB = settings.mqtt.topic_sub
MQTT_TOPIC_PUB = settings.mqtt.topic_pub

# 内嵌 Broker 配置
EMBEDDED_BROKER = settings.broker.enabled
BROKER_BIND_HOST = settings.broker.bind_host
BROKER_BIND_PORT = settings.broker.bind_port

# 心跳与看门狗
HEARTBEAT_TIMEOUT = settings.game.heartbeat_timeout
WATCHDOG_INTERVAL = settings.game.watchdog_interval
UI_HOT_RELOAD = settings.game.ui_hot_reload

# 消息格式
MSG_LENGTH = settings.message.msg_length
NODE_ID_LENGTH = settings.message.node_id_length

BROKER_READY = Event()

_INSTALLED_AUDIO = _Path("/usr/local/share/cluster/audio")
if _INSTALLED_AUDIO.exists():
    AUDIO_DIR = str(_INSTALLED_AUDIO)
    # 已安装：日志写到用户家目录
    LOG_DIR = str(_Path.home() / ".local" / "share" / "cluster" / "log")
else:
    AUDIO_DIR = str(  # pyright: ignore[reportConstantRedefinition]
        _Path(__file__).parent.parent / "resources" / "audio"
    )
    # 开发环境：日志写到相对路径
    LOG_DIR = "log"  # pyright: ignore[reportConstantRedefinition]


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

# frpc 配置
FRPC_SERVER_ADDR = settings.frpc.server_addr
FRPC_SERVER_PORT = settings.frpc.server_port
FRPC_AUTH_TOKEN = settings.frpc.auth_token
FRPC_PROXIES = settings.frpc.proxies

__all__ = [
    "settings",
    "MQTT_BROKER",
    "MQTT_PORT",
    "MQTT_QOS",
    "MQTT_TOPIC_SUB",
    "MQTT_TOPIC_PUB",
    "EMBEDDED_BROKER",
    "BROKER_BIND_HOST",
    "BROKER_BIND_PORT",
    "HEARTBEAT_TIMEOUT",
    "WATCHDOG_INTERVAL",
    "MSG_LENGTH",
    "NODE_ID_LENGTH",
    "AUDIO_DIR",
    "LOG_DIR",
    "AUDIO_FILES",
    "BROKER_READY",
    "FRPC_SERVER_ADDR",
    "FRPC_SERVER_PORT",
    "FRPC_AUTH_TOKEN",
    "FRPC_PROXIES",
]
