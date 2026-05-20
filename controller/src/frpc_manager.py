import asyncio
import json
import logging
import platform
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


def _frpc_binary_path() -> Path | None:
    """根据当前架构返回 frpc 二进制路径。"""
    arch = platform.machine()
    if arch == "x86_64":
        arch_dir = "amd64"
    elif arch in ("aarch64", "arm64"):
        arch_dir = "arm64"
    else:
        logger.warning(f"不支持的架构: {arch}，无法运行 frpc")
        return None

    installed = Path("/usr/local/share/cluster/frpc")
    if installed.exists():
        return installed / arch_dir / "frpc"

    dev = Path(__file__).parent.parent / "resources" / "frpc" / arch_dir / "frpc"
    if dev.exists():
        return dev

    return None


def _build_frpc_config(config: dict[Any, Any]) -> str:
    """从配置字典生成 frpc.toml 内容。"""
    lines = [
        f'serverAddr = "{config.get("server_addr", "")}"',
        f"serverPort = {config.get('server_port', 7000)}",
    ]
    token = config.get("auth_token", "")
    if token:
        lines.append(f'auth.token = "{token}"')
    lines.append("")

    proxies = config.get("proxies", [])
    if isinstance(proxies, str):
        try:
            proxies = json.loads(proxies)
        except (json.JSONDecodeError, TypeError):
            proxies = []

    for p in proxies:
        lines.append("[[proxies]]")
        lines.append(f'name = "{p.get("name", "")}"')
        lines.append(f'type = "{p.get("type", "tcp")}"')
        lines.append(f'localIP = "{p.get("local_ip", "127.0.0.1")}"')
        lines.append(f"localPort = {p.get('local_port', 80)}")
        lines.append(f"remotePort = {p.get('remote_port', 8080)}")
        lines.append("")

    return "\n".join(lines)


class FrpcManager(QObject):
    """管理 frpc 进程的启动、停止和日志输出。"""

    status_changed = Signal(bool)
    log_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent: "QObject | None" = None) -> None:
        super().__init__(parent)
        self._process: asyncio.subprocess.Process | None = None
        self._running = False
        self._config_path: Path = Path(__file__).parent.parent / "frpc.toml"

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, config: dict[Any, Any]) -> None:
        """写入配置文件并启动 frpc。"""
        if self._running:
            logger.warning("frpc 已在运行中")
            return

        binary = _frpc_binary_path()
        if binary is None:
            self.error_occurred.emit(
                "无法找到 frpc 二进制文件（不支持的架构或文件缺失）"
            )
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
        self._running = True
        self.status_changed.emit(True)

        task = asyncio.create_task(self._run_process(binary))
        self._task = task

    def stop(self) -> None:
        """终止 frpc 进程。"""
        if not self._running or self._process is None:
            return
        logger.info("正在停止 frpc...")
        self._process.terminate()
        # 不在这里设置 _running = False，由 _run_process 的 finally 处理

    async def _run_process(self, binary: Path) -> None:
        """异步子进程，读取 frpc 的 stdout/stderr。"""
        try:
            self._process = await asyncio.create_subprocess_exec(
                str(binary),
                "-c",
                str(self._config_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self.log_received.emit(f"[系统] frpc 已启动，PID: {self._process.pid}")

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
            raise
        except Exception as e:
            self.error_occurred.emit(f"frpc 运行时错误: {e}")
            logger.error(f"frpc 运行时错误: {e}", exc_info=True)
        finally:
            self._running = False
            self._process = None
            self.status_changed.emit(False)
