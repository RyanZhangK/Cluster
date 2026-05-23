import asyncio
import logging
import platform
from enum import Enum, auto
from pathlib import Path
from typing import Any

import toml
from PySide6.QtCore import QObject, Signal

from .config import settings

logger = logging.getLogger(__name__)


class FrpcState(Enum):
    IDLE = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()


def _frpc_binary_path() -> Path | None:
    arch = platform.machine()
    if arch == "x86_64":
        arch_dir = "amd64"
    elif arch in ("aarch64", "arm64"):
        arch_dir = "arm64"
    else:
        logger.warning(f"不支持的架构: {arch}")
        return None

    installed = Path("/usr/local/share/cluster/frpc")
    if installed.exists():
        return installed / arch_dir / "frpc"

    if settings.controller.dev:
        dev = Path(__file__).parent.parent / "resources" / "frpc" / arch_dir / "frpc"
        if dev.exists():
            return dev

    return None


def _build_frpc_config(config: dict[str, Any]) -> str:
    proxies = config.get("proxies", [])
    data: dict[str, Any] = {
        "serverAddr": config.get("server_addr", ""),
        "serverPort": config.get("server_port", 7000),
    }
    token = config.get("auth_token", "")
    if token:
        data["auth"] = {"token": token}

    if proxies:
        data["proxies"] = [
            {
                "name": p.get("name", ""),
                "type": p.get("type", "tcp"),
                "localIP": p.get("local_ip", "127.0.0.1"),
                "localPort": p.get("local_port", 80),
                "remotePort": p.get("remote_port", 8080),
            }
            for p in proxies
        ]

    return toml.dumps(data)


class FrpcManager(QObject):
    status_changed = Signal(bool)
    log_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task[None] | None = None
        self._config_path: Path = Path(__file__).parent.parent / "frpc.toml"
        self._state = FrpcState.IDLE

    @property
    def is_running(self) -> bool:
        return self._state == FrpcState.RUNNING

    def start(self, config: dict[str, Any]) -> None:
        if self._state != FrpcState.IDLE:
            logger.warning("frpc 已在运行或正在启动中")
            return

        binary = _frpc_binary_path()
        if binary is None:
            self.error_occurred.emit("无法找到 frpc 二进制文件")
            return

        if not binary.exists():
            self.error_occurred.emit(f"frpc 二进制文件不存在: {binary}")
            return

        try:
            binary.chmod(0o755)
        except OSError:
            pass

        toml_content = _build_frpc_config(config)
        try:
            self._config_path.write_text(toml_content, encoding="utf-8")
        except OSError as e:
            self.error_occurred.emit(f"无法写入配置文件: {e}")
            return

        logger.info(f"frpc 配置已写入: {self._config_path}")
        self._state = FrpcState.STARTING
        self._task = asyncio.create_task(self._run(binary))

    def stop(self) -> None:
        if self._state not in (FrpcState.RUNNING, FrpcState.STARTING):
            return

        logger.info("正在停止 frpc...")
        self._state = FrpcState.STOPPING

        if self._process is not None and self._process.returncode is None:
            self._process.terminate()

        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _run(self, binary: Path) -> None:
        try:
            self._process = await asyncio.create_subprocess_exec(
                str(binary),
                "-c",
                str(self._config_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self.log_received.emit(f"[系统] frpc 已启动，PID: {self._process.pid}")

            if self._state == FrpcState.STARTING:
                self._state = FrpcState.RUNNING
                self.status_changed.emit(True)

            assert self._process.stdout is not None
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    self.log_received.emit(text)

            await self._process.wait()
            exit_code = self._process.returncode
            if exit_code != 0:
                self.log_received.emit(f"[系统] frpc 进程退出，返回码: {exit_code}")
            else:
                self.log_received.emit("[系统] frpc 进程已正常退出")
        except asyncio.CancelledError:
            if self._process and self._process.returncode is None:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            self.log_received.emit("[系统] frpc 已停止")
        except Exception as e:
            self.error_occurred.emit(f"frpc 运行时错误: {e}")
            logger.error(f"frpc 运行时错误: {e}", exc_info=True)
        finally:
            self._process = None
            self._state = FrpcState.IDLE
            self.status_changed.emit(False)
