import asyncio
import json
import logging
import platform
from enum import Enum, auto
from pathlib import Path
from typing import Any

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


def _frpc_config_path() -> Path:
    config_dir = Path.home() / ".config" / "cluster"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "frpc.conf"


def _build_cli_args(server: dict[str, Any], proxy: dict[str, Any]) -> list[str]:
    args = [
        proxy.get("type", "tcp"),
        "-s", str(server.get("server_addr", "")),
        "-P", str(server.get("server_port", 7000)),
    ]
    token = server.get("auth_token", "")
    if token:
        args.extend(["-t", str(token)])
    args.extend([
        "-n", str(proxy.get("name", "")),
        "-i", str(proxy.get("local_ip", "127.0.0.1")),
        "-l", str(proxy.get("local_port", 80)),
        "-r", str(proxy.get("remote_port", 8080)),
    ])
    return args


class FrpcManager(QObject):
    status_changed = Signal(bool)
    log_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._processes: list[asyncio.subprocess.Process] = []
        self._tasks: list[asyncio.Task[None]] = []
        self._config_path = _frpc_config_path()
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

        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as e:
            self.error_occurred.emit(f"无法写入配置文件: {e}")
            return

        proxies = config.get("proxies", [])
        if not proxies:
            self.error_occurred.emit("没有配置任何代理隧道")
            return

        self._state = FrpcState.STARTING
        for proxy in proxies:
            task = asyncio.create_task(self._run(binary, config, proxy))
            self._tasks.append(task)

    def stop(self) -> None:
        if self._state not in (FrpcState.RUNNING, FrpcState.STARTING):
            return

        logger.info("正在停止 frpc...")
        self._state = FrpcState.STOPPING

        for proc in self._processes:
            if proc.returncode is None:
                proc.terminate()

        for task in self._tasks:
            if not task.done():
                task.cancel()

    async def _run(
        self, binary: Path, server: dict[str, Any], proxy: dict[str, Any]
    ) -> None:
        args = _build_cli_args(server, proxy)
        name = proxy.get("name", "unknown")
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                str(binary),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self._processes.append(proc)
            self.log_received.emit(f"[系统] 隧道 {name} 已启动，PID: {proc.pid}")

            if self._state == FrpcState.STARTING:
                self._state = FrpcState.RUNNING
                self.status_changed.emit(True)

            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    self.log_received.emit(f"[{name}] {text}")

            await proc.wait()
            exit_code = proc.returncode
            if exit_code != 0:
                self.log_received.emit(f"[系统] 隧道 {name} 进程退出，返回码: {exit_code}")
            else:
                self.log_received.emit(f"[系统] 隧道 {name} 进程已正常退出")
        except asyncio.CancelledError:
            if proc is not None and proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
            self.log_received.emit(f"[系统] 隧道 {name} 已停止")
        except Exception as e:
            self.error_occurred.emit(f"隧道 {name} 运行时错误: {e}")
            logger.error(f"frpc 运行时错误: {e}", exc_info=True)
        finally:
            if proc is not None and proc in self._processes:
                self._processes.remove(proc)
            if not self._processes and self._state != FrpcState.STOPPING:
                self._state = FrpcState.IDLE
                self.status_changed.emit(False)
