import sys
import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import qasync
from PySide6.QtWidgets import QApplication

from .config import LOG_DIR, EMBEDDED_BROKER
from .event_bus import EventBus
from .node_manager import NodeManager
from .mqtt_client import MQTTClient
from .audio_player import AudioPlayer
from .embedded_broker import EmbeddedBroker
from .UI import MainWindow


def setup_logging() -> None:
    """配置日志：TimedRotatingFileHandler 写入 log/ 目录，按天滚动。"""
    log_dir = Path(__file__).parent / LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "controller.log"

    handler = TimedRotatingFileHandler(
        str(log_path), when="midnight", backupCount=7, encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)


    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler, console_handler],
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    app = QApplication(sys.argv)

    # 构建依赖图（手动 DI）
    event_bus = EventBus()
    node_manager = NodeManager(event_bus)
    audio_player = AudioPlayer()
    mqtt_client = MQTTClient(node_manager, event_bus)

    # 创建并展示主窗口
    window = MainWindow(node_manager, event_bus, audio_player)
    window.show()

    # qasync：将 asyncio 事件循环与 Qt 事件循环融合
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        # 内嵌 Broker 优先启动，让客户端连接时已可用
        if EMBEDDED_BROKER:
            broker = EmbeddedBroker()
            loop.create_task(broker.run(), name="embedded_broker")
            # 给 Broker 一点点启动时间（amqtt.start() 是异步的，但客户端立即连接可能竞态）
            # MQTTClient 自带重试机制，即使首次失败也会自动重连，所以无需精确同步

        loop.create_task(mqtt_client.run(), name="mqtt_client")
        loop.create_task(node_manager.heartbeat_watchdog(), name="heartbeat_watchdog")
        logger.info("Controller started. Listening on node/status ...")
        loop.run_forever()


if __name__ == "__main__":
    main()
