import asyncio
import logging

from amqtt.broker import Broker

from .config import BROKER_BIND_HOST, BROKER_BIND_PORT, BROKER_READY

logger = logging.getLogger(__name__)


def _build_config() -> dict:
    """构建 amqtt Broker 配置字典。"""
    return {
        "listeners": {
            "default": {
                "type": "tcp",
                "bind": f"{BROKER_BIND_HOST}:{BROKER_BIND_PORT}",
                "max_connections": 100,
            }
        },
        "plugins": {
            "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                "allow_anonymous": True
            },
            "amqtt.plugins.sys.broker.BrokerSysPlugin": {
                "sys_interval": 0,
            },
        },
    }


class EmbeddedBroker:
    """
    内嵌 MQTT Broker，与 controller 同进程同事件循环运行。
    生产环境通过 frp 反代 1883 端口暴露给外部 ESP8266 节点。
    """

    def __init__(self) -> None:
        self._broker: Broker | None = None

    async def run(self) -> None:
        """启动 Broker 并保持运行。被 cancel 时优雅关闭。"""
        config = _build_config()
        self._broker = Broker(config)
        try:
            await self._broker.start()
            BROKER_READY.set()
            logger.info(
                f"内嵌 MQTT Broker 已启动: {BROKER_BIND_HOST}:{BROKER_BIND_PORT}"
            )
            # 持续保持任务存活，等待 cancel
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("内嵌 Broker 收到关闭信号")
            raise
        except Exception as e:
            logger.error(f"内嵌 Broker 启动失败: {e}")
            raise
        finally:
            BROKER_READY.clear()
            if self._broker is not None:
                try:
                    await self._broker.shutdown()
                    logger.info("内嵌 Broker 已关闭")
                except Exception as e:
                    logger.error(f"内嵌 Broker 关闭时出错: {e}")
