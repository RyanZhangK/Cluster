"""QProcess-backed esptool worker for flashing ESP8266 firmware."""

import re
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal


class FlashWorker(QObject):
    """Runs esptool in a QProcess, emitting progress and log signals."""

    progress_changed = Signal(int)          # 0–100
    log_message = Signal(str)               # single log line
    flash_finished = Signal(bool, str)      # (success, summary message)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._process: QProcess | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_flash(
        self,
        port: str,
        firmware_path: str,
        baud: int = 460800,
        erase: bool = False,
    ) -> None:
        """Launch the esptool subprocess to write *firmware_path* to *port*."""
        args = [
            "-m", "esptool",
            "--chip", "auto",
            "--port", port,
            "--baud", str(baud),
            "--before", "default_reset",
            "--after", "hard_reset",
            "write_flash",
        ]
        if erase:
            args.append("--erase-all")
        args.extend(["0x00000", str(firmware_path)])

        self._process = QProcess(self)
        self._process.setProgram(sys.executable)
        self._process.setArguments(args)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)

        # esptool writes progress/status to stderr
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self.log_message.emit(
            f"[{_now()}] 开始烧录 — 端口 {port}, 固件 {Path(firmware_path).name}"
        )
        self._process.start()

    def cancel(self) -> None:
        """Kill a running flash operation."""
        if self._process and self._process.state() != QProcess.NotRunning:
            self._process.kill()
            self.log_message.emit(f"[{_now()}] 烧录已取消")

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardError().data().decode(
            errors="replace"
        )
        for line in data.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            self.log_message.emit(stripped)
            # esptool progress: "Writing at 0x... (33 %)"
            pct = _parse_progress(stripped)
            if pct >= 0:
                self.progress_changed.emit(pct)

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data().decode(
            errors="replace"
        )
        for line in data.splitlines():
            stripped = line.strip()
            if stripped:
                self.log_message.emit(stripped)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        if exit_code == 0:
            self.progress_changed.emit(100)
            self.log_message.emit(f"[{_now()}] ✔ 烧录成功!")
            self.flash_finished.emit(True, "固件烧录完成")
        else:
            self.flash_finished.emit(False, f"esptool 退出码 {exit_code}，请查看日志")

    def _on_error(self, error: QProcess.ProcessError) -> None:
        messages = {
            QProcess.FailedToStart: (
                "无法启动 esptool。请确认 esptool 已安装 (uv sync --group flasher)"
            ),
            QProcess.Timedout: "烧录超时，请检查设备连接",
        }
        msg = messages.get(error, f"烧录进程错误 (code={error})")

        # Permission errors on Linux
        if error == QProcess.FailedToStart:
            msg += (
                "\n提示: Linux 用户请确保当前用户已加入 dialout 组: "
                "sudo usermod -aG dialout $USER"
            )

        self.log_message.emit(f"[{_now()}] ❌ {msg}")
        self.flash_finished.emit(False, msg)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_PROGRESS_RE = re.compile(r"\((\d+)\s*%\)")


def _parse_progress(line: str) -> int:
    """Extract a progress percentage from an esptool stderr line, or -1."""
    m = _PROGRESS_RE.search(line)
    if m:
        return int(m.group(1))
    return -1


def _now() -> str:
    """Timestamp for log lines."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
