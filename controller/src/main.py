import asyncio
import importlib
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import qasync
from PySide6.QtWidgets import QApplication

from . import UI
from .audio_player import AudioPlayer
from .config import EMBEDDED_BROKER, LOG_DIR, settings
from .embedded_broker import EmbeddedBroker
from .event_bus import EventBus
from .mqtt_client import MQTTClient
from .node_manager import NodeManager


def setup_logging() -> None:
    """配置日志：TimedRotatingFileHandler 写入 log/ 目录，按天滚动。"""
    log_dir = Path(__file__).parent.parent / LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "controller.log"

    handler = TimedRotatingFileHandler(
        str(log_path), when="midnight", backupCount=7, encoding="utf-8"
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler, console_handler],
    )


async def ui_hot_reload_watcher(node_manager, event_bus, audio_player):
    """每秒检查一次 UI.py 的修改时间"""
    logger = logging.getLogger("HotReload")

    ui_file = Path(__file__).parent / "UI.py"
    if not ui_file.exists():
        ui_file = Path(__file__).parent / "UI" / "__init__.py"

    if not ui_file.exists():
        logger.warning(f"无法找到 UI 文件: {ui_file}，热重载未激活。")
        return

    last_mtime = ui_file.stat().st_mtime
    logger.info(f"UI 热重载已激活，正在监听: {ui_file.name}")

    while True:
        await asyncio.sleep(1)
        try:
            current_mtime = ui_file.stat().st_mtime
            if current_mtime > last_mtime:
                last_mtime = current_mtime
                logger.info("检测到 UI 代码变动，正在重新加载...")

                app = QApplication.instance()
                _window = None
                geometry = None

                if isinstance(app, QApplication):
                    for widget in app.topLevelWidgets():
                        if (
                            widget.__class__.__name__ == "MainWindow"
                            and widget.isVisible()
                        ):
                            _window = widget
                            geometry = _window.geometry()
                            break

                importlib.reload(UI)

                if _window:
                    _window.close()
                    _window.deleteLater()

                new_window = UI.MainWindow(node_manager, event_bus, audio_player)

                if geometry:
                    new_window.setGeometry(geometry)

                new_window.show()
                logger.info("UI 热重载完成！")
        except Exception as e:
            logger.error(f"热重载失败: {e}", exc_info=True)


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
    window = UI.MainWindow(node_manager, event_bus, audio_player)
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
        if settings.game.ui_hot_reload:
            loop.create_task(
                ui_hot_reload_watcher(node_manager, event_bus, audio_player),
                name="ui_hot_reload",
            )
        logger.info("Controller started. Listening on node/status ...")
        loop.run_forever()


if __name__ == "__main__":
    main()
