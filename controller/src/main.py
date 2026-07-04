import asyncio
import importlib
import json
import logging
import signal
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import qasync
import watchdog.events
import watchdog.observers
from PySide6.QtWidgets import QApplication

from controller.src import UI
from controller.src.audio_player import AudioPlayer
from controller.src.config import EMBEDDED_BROKER, LOG_DIR, MQTT_TOPIC_CMD, settings
from controller.src.embedded_broker import EmbeddedBroker
from controller.src.event_bus import EventBus
from controller.src.frpc_manager import FrpcManager, _frpc_config_path
from controller.src.mqtt_client import MQTTClient
from controller.src.node_manager import NodeManager


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


async def ui_hot_reload_watcher(
    node_manager: NodeManager,
    event_bus: EventBus,
    audio_player: AudioPlayer,
    frpc_manager: "FrpcManager",
):
    """使用 inotify 监听 UI 文件改动，变更立刻 reload"""
    logger = logging.getLogger("HotReload")

    ui_file = Path(__file__).resolve().parent / "UI.py"
    if not ui_file.exists():
        ui_file = Path(__file__).resolve().parent / "__init__.py"

    if not ui_file.exists():
        logger.warning(f"无法找到 UI 文件: {ui_file}，热重载未激活。")
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[None] = asyncio.Queue()

    class _Handler(watchdog.events.FileSystemEventHandler):
        def on_modified(
            self,
            event: watchdog.events.DirModifiedEvent | watchdog.events.FileModifiedEvent,
        ):
            if event.is_directory:
                return
            loop.call_soon_threadsafe(queue.put_nowait, None)

    observer = watchdog.observers.Observer()
    observer.schedule(
        _Handler(),
        str(ui_file.parent),
        recursive=(ui_file.name == "__init__.py"),
    )
    observer.start()
    logger.info(f"UI 热重载已激活，正在监听: {ui_file}")

    try:
        while True:
            await queue.get()
            try:
                while True:
                    await asyncio.wait_for(queue.get(), timeout=0.15)
            except asyncio.TimeoutError:
                pass

            logger.info("检测到 UI 代码变动，正在重新加载...")

            app = QApplication.instance()
            _window = None
            geometry = None

            if isinstance(app, QApplication):
                for widget in app.topLevelWidgets():
                    if widget.__class__.__name__ == "MainWindow" and widget.isVisible():
                        _window = widget
                        geometry = _window.geometry()
                        break

            importlib.reload(UI)

            if _window:
                _window.close()
                _window.deleteLater()

            new_window = UI.MainWindow(
                node_manager, event_bus, audio_player, frpc_manager
            )

            if geometry:
                new_window.setGeometry(geometry)

            new_window.show()
            logger.info("UI 热重载完成！")
    finally:
        observer.stop()
        observer.join(timeout=1)


async def _auto_start_frpc(frpc_manager: FrpcManager) -> None:
    """如果 frpc 配置文件存在且有代理隧道配置，自动启动 frpc"""
    logger = logging.getLogger(__name__)

    config_path = _frpc_config_path()
    if not config_path.exists():
        logger.info("frpc 配置文件不存在，跳过自动启动")
        return

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"读取 frpc 配置文件失败: {e}")
        return

    proxies = config.get("proxies", [])
    if not proxies:
        logger.info("frpc 配置中没有代理隧道，跳过自动启动")
        return

    logger.info(f"检测到 frpc 配置 ({len(proxies)} 个隧道)，正在自动启动...")
    frpc_manager.start(config)


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    app = QApplication(sys.argv)

    # 构建依赖图（手动 DI）
    event_bus = EventBus()

    # Qt 日志处理器：将日志管道接入 EventBus，供调试面板消费
    class _QtLogHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            self.setFormatter(formatter)

        def emit(self, record: logging.LogRecord) -> None:
            try:
                msg = self.format(record)
                event_bus.log_received.emit(msg, record.levelno)
            except Exception:
                self.handleError(record)

    _qt_handler = _QtLogHandler()
    _qt_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(_qt_handler)

    node_manager = NodeManager(event_bus)
    audio_player = AudioPlayer()
    mqtt_client = MQTTClient(node_manager, event_bus)
    frpc_manager = FrpcManager()

    # 场馆锁定信号 → MQTT 下发桥接
    event_bus.venue_lock_changed.connect(
        lambda locked: mqtt_client.publish(
            MQTT_TOPIC_CMD, "LOCK:1" if locked else "LOCK:0"
        )
    )

    # 创建并展示主窗口
    window = UI.MainWindow(node_manager, event_bus, audio_player, frpc_manager)
    window.show()

    # qasync：将 asyncio 事件循环与 Qt 事件循环融合
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    async def _shutdown() -> None:
        logger.info("正在关闭所有服务...")
        try:
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.wait(tasks, timeout=5)
        except Exception:
            logger.exception("关闭时发生错误")
        finally:
            logger.info("所有服务已关闭。")
            app.quit()

    def _schedule_shutdown(signum: int, _):
        logger.info(f"接收到信号 {{{signum}}}，正在关闭程序...")
        loop.call_soon_threadsafe(lambda: asyncio.create_task(_shutdown()))

    signal.signal(signal.SIGINT, _schedule_shutdown)
    signal.signal(signal.SIGTERM, _schedule_shutdown)

    with loop:
        if EMBEDDED_BROKER:
            broker = EmbeddedBroker()
            loop.create_task(broker.run(), name="embedded_broker")

        loop.create_task(mqtt_client.run(), name="mqtt_client")
        loop.create_task(node_manager.heartbeat_watchdog(), name="heartbeat_watchdog")
        loop.create_task(_auto_start_frpc(frpc_manager), name="frpc_auto_start")
        if settings.controller.ui_hot_reload:
            loop.create_task(
                ui_hot_reload_watcher(
                    node_manager, event_bus, audio_player, frpc_manager
                ),
                name="ui_hot_reload",
            )
        logger.info("Controller started. Listening on node/status ...")
        loop.run_forever()


if __name__ == "__main__":
    main()
