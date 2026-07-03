"""Main window for the Cluster Firmware Flasher."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tools.flasher.flash_worker import FlashWorker
from tools.flasher.serial_scanner import list_ports
from tools.flasher.styles import (
    C_BG,
    C_TEXT,
    C_TEXT_SEC,
    C_PRIMARY,
    C_SUCCESS,
    C_DANGER,
    btn_style,
    combo_style,
    input_style,
    progress_style,
    section_label_style,
    log_area_style,
)

BAUD_RATES = ["460800", "115200", "921600", "230400", "74880"]


class MainWindow(QMainWindow):
    """Firmware flashing GUI for Cluster ESP8266 nodes."""

    def __init__(self) -> None:
        super().__init__()
        self._worker: FlashWorker = FlashWorker(self)
        self._flashing = False

        self.setWindowTitle("Cluster Firmware Flasher")
        self.setMinimumSize(580, 520)
        self.setStyleSheet(f"QMainWindow {{ background-color: {C_BG}; }}")

        central = QWidget()
        self.setCentralWidget(central)
        self._build_ui(central)
        self._wire_signals()

        # Initial port scan
        self._rescan_ports()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, root: QWidget) -> None:
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        # ── Serial port row ──────────────────────────────────────────
        layout.addWidget(self._label("串口"))
        row = QHBoxLayout()
        row.setSpacing(8)

        self.port_combo = QComboBox()
        self.port_combo.setStyleSheet(combo_style())
        self.port_combo.setMinimumWidth(300)
        row.addWidget(self.port_combo, 1)

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setStyleSheet(btn_style(C_TEXT_SEC))
        self.btn_refresh.setFixedWidth(64)
        row.addWidget(self.btn_refresh)

        layout.addLayout(row)

        # ── Firmware file row ────────────────────────────────────────
        layout.addWidget(self._label("固件文件"))
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.firmware_path = QLineEdit()
        self.firmware_path.setReadOnly(True)
        self.firmware_path.setPlaceholderText("选择 .bin 固件文件 …")
        self.firmware_path.setStyleSheet(input_style())
        row2.addWidget(self.firmware_path, 1)

        self.btn_browse = QPushButton("浏览")
        self.btn_browse.setStyleSheet(btn_style(C_TEXT_SEC))
        self.btn_browse.setFixedWidth(64)
        row2.addWidget(self.btn_browse)

        layout.addLayout(row2)

        # ── Baud rate + erase row ────────────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(8)

        baud_group = QVBoxLayout()
        baud_group.setSpacing(2)
        baud_group.addWidget(self._label("波特率"))
        self.baud_combo = QComboBox()
        self.baud_combo.setStyleSheet(combo_style())
        self.baud_combo.addItems(BAUD_RATES)
        self.baud_combo.setCurrentIndex(0)  # 460800 default
        baud_group.addWidget(self.baud_combo)
        row3.addLayout(baud_group)

        row3.addStretch()

        self.erase_check = QCheckBox("烧录前全片擦除 (--erase-all)")
        self.erase_check.setStyleSheet(f"color: {C_TEXT_SEC}; font-size: 12px;")
        row3.addWidget(self.erase_check, alignment=Qt.AlignmentFlag.AlignBottom)

        layout.addLayout(row3)

        # ── Flash button ─────────────────────────────────────────────
        self.btn_flash = QPushButton("开始烧录")
        flash_height = 42
        self.btn_flash.setMinimumHeight(flash_height)
        self.btn_flash.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {C_PRIMARY};
                color: {C_TEXT};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{ background-color: {C_PRIMARY}cc; }}
            QPushButton:pressed {{ background-color: {C_PRIMARY}99; }}
            QPushButton:disabled {{
                background-color: {C_PRIMARY}44;
                color: {C_TEXT_SEC};
            }}
            """
        )
        layout.addWidget(self.btn_flash)

        # ── Progress bar ─────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(progress_style(C_PRIMARY))
        layout.addWidget(self.progress_bar)

        # ── Log area ─────────────────────────────────────────────────
        layout.addWidget(self._label("烧录日志"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(log_area_style())
        self.log_area.setMinimumHeight(140)
        layout.addWidget(self.log_area, 1)

        # ── Status bar ───────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(
            f"""
            QStatusBar {{
                color: {C_TEXT_SEC};
                font-size: 11px;
                background: transparent;
                border-top: 1px solid {C_TEXT_SEC}22;
            }}
            """
        )
        self.status_bar.showMessage("就绪")
        self.setStatusBar(self.status_bar)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self.btn_refresh.clicked.connect(self._rescan_ports)
        self.btn_browse.clicked.connect(self._browse_firmware)
        self.btn_flash.clicked.connect(self._start_flash)

        self.port_combo.currentIndexChanged.connect(self._update_flash_button)
        # Also need to update when firmware path changes — but we set it
        # programmatically, so the button state is checked in _browse_firmware.

        self._worker.progress_changed.connect(self._on_progress)
        self._worker.log_message.connect(self._on_log)
        self._worker.flash_finished.connect(self._on_flash_done)

    # ------------------------------------------------------------------
    # Slots – user actions
    # ------------------------------------------------------------------

    def _rescan_ports(self) -> None:
        self.port_combo.clear()
        ports = list_ports()
        if not ports:
            self.port_combo.addItem("(未检测到串口)")
            self._update_flash_button()
            return
        for p in ports:
            self.port_combo.addItem(p.display_name(), p.device)
        self._update_flash_button()

    def _browse_firmware(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择固件文件",
            "",
            "固件文件 (*.bin);;所有文件 (*)",
        )
        if path:
            self.firmware_path.setText(path)
        self._update_flash_button()

    def _start_flash(self) -> None:
        port = self.port_combo.currentData()
        firmware = self.firmware_path.text().strip()
        if not port or port.startswith("(") or not firmware:
            return

        # Validate firmware file
        fw = Path(firmware)
        if not fw.exists():
            self._append_log(f"[{_now()}] ❌ 固件文件不存在: {firmware}")
            self.status_bar.showMessage("固件文件不存在")
            return
        if fw.suffix.lower() != ".bin":
            self._append_log(f"[{_now()}] ⚠ 文件扩展名不是 .bin，仍尝试烧录")

        baud = int(self.baud_combo.currentText())
        erase = self.erase_check.isChecked()

        self._set_ui_enabled(False)
        self._flashing = True
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(progress_style(C_PRIMARY))
        self.log_area.clear()
        self.status_bar.showMessage("正在烧录 …")

        self._worker.start_flash(port, firmware, baud, erase)

    # ------------------------------------------------------------------
    # Slots – worker feedback
    # ------------------------------------------------------------------

    def _on_progress(self, pct: int) -> None:
        self.progress_bar.setValue(pct)

    def _on_log(self, line: str) -> None:
        self._append_log(line)

    def _on_flash_done(self, success: bool, message: str) -> None:
        self._flashing = False
        self._set_ui_enabled(True)
        color = C_SUCCESS if success else C_DANGER
        self.progress_bar.setStyleSheet(progress_style(color))
        self.status_bar.showMessage(message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_flash_button(self) -> None:
        if self._flashing:
            return
        port = self.port_combo.currentData()
        firmware = self.firmware_path.text().strip()
        ok = bool(port and not str(port).startswith("(") and firmware)
        self.btn_flash.setEnabled(ok)

    def _set_ui_enabled(self, enabled: bool) -> None:
        self.port_combo.setEnabled(enabled)
        self.btn_refresh.setEnabled(enabled)
        self.firmware_path.setEnabled(enabled)
        self.btn_browse.setEnabled(enabled)
        self.baud_combo.setEnabled(enabled)
        self.erase_check.setEnabled(enabled)
        self.btn_flash.setEnabled(enabled)

    def _append_log(self, line: str) -> None:
        self.log_area.append(line)
        # Auto-scroll to bottom
        sb = self.log_area.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(section_label_style())
        return lbl


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")
