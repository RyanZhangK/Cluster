"""Debug page for Cluster UI — system logs and MQTT message monitor."""

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    C_BG,
    C_BORDER,
    C_TEXT,
    C_TEXT_MUTED,
    btn_style,
    combo_style,
    toggle_btn_style,
)
from .widgets import Card, add_section_label


def build_debug_page(parent: Any) -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background-color: {C_BG};")
    layout = QHBoxLayout(page)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(16)

    # ── 左：系统日志 ────────────────────────────────────────────────────────
    log_card = Card()
    log_layout = QVBoxLayout(log_card)
    log_layout.setContentsMargins(20, 16, 20, 18)
    log_layout.setSpacing(10)
    add_section_label(log_layout, "系统日志")

    log_toolbar = QHBoxLayout()
    log_toolbar.setSpacing(8)
    parent._log_level_combo = QComboBox()
    parent._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
    parent._log_level_combo.setCurrentText("INFO")
    parent._log_level_combo.setStyleSheet(combo_style())
    parent._log_level_combo.setFixedWidth(110)
    parent._log_level_combo.currentTextChanged.connect(parent._on_log_level_changed)
    log_toolbar.addWidget(parent._log_level_combo)
    log_toolbar.addStretch()
    log_clear_btn = QPushButton("清空")
    log_clear_btn.setFixedHeight(30)
    log_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    log_clear_btn.setStyleSheet(btn_style(C_TEXT_MUTED))
    log_clear_btn.clicked.connect(parent._on_clear_log)
    log_toolbar.addWidget(log_clear_btn)
    log_layout.addLayout(log_toolbar)

    parent._log_view = QTextEdit()
    parent._log_view.setReadOnly(True)
    font = QFont("Consolas, Monaco, monospace")
    font.setStyleHint(QFont.StyleHint.Monospace)
    parent._log_view.setFont(font)
    parent._log_view.setStyleSheet(f"""
        QTextEdit {{
            background-color: #1a1a1a;
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 10px;
            font-size: 12px;
        }}
    """)
    log_layout.addWidget(parent._log_view)

    layout.addWidget(log_card, 1)

    # ── 右：MQTT 消息 ──────────────────────────────────────────────────────
    mqtt_card = Card()
    mqtt_layout = QVBoxLayout(mqtt_card)
    mqtt_layout.setContentsMargins(20, 16, 20, 18)
    mqtt_layout.setSpacing(10)
    add_section_label(mqtt_layout, "MQTT 消息")

    mqtt_toolbar = QHBoxLayout()
    mqtt_toolbar.setSpacing(8)
    parent._mqtt_pause_btn = QPushButton("暂停")
    parent._mqtt_pause_btn.setCheckable(True)
    parent._mqtt_pause_btn.setFixedHeight(30)
    parent._mqtt_pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._mqtt_pause_btn.setStyleSheet(toggle_btn_style(False))
    parent._mqtt_pause_btn.clicked.connect(parent._on_mqtt_pause_toggle)
    mqtt_toolbar.addWidget(parent._mqtt_pause_btn)
    parent._mqtt_count_label = QLabel("0 条")
    parent._mqtt_count_label.setStyleSheet(
        f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent;"
    )
    mqtt_toolbar.addWidget(parent._mqtt_count_label)
    mqtt_toolbar.addStretch()
    mqtt_clear_btn = QPushButton("清空")
    mqtt_clear_btn.setFixedHeight(30)
    mqtt_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    mqtt_clear_btn.setStyleSheet(btn_style(C_TEXT_MUTED))
    mqtt_clear_btn.clicked.connect(parent._on_clear_mqtt)
    mqtt_toolbar.addWidget(mqtt_clear_btn)
    mqtt_layout.addLayout(mqtt_toolbar)

    parent._mqtt_view = QTextEdit()
    parent._mqtt_view.setReadOnly(True)
    font2 = QFont("Consolas, Monaco, monospace")
    font2.setStyleHint(QFont.StyleHint.Monospace)
    parent._mqtt_view.setFont(font2)
    parent._mqtt_view.setStyleSheet(f"""
        QTextEdit {{
            background-color: #1a1a1a;
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 10px;
            font-size: 12px;
        }}
    """)
    mqtt_layout.addWidget(parent._mqtt_view)

    layout.addWidget(mqtt_card, 1)

    parent._mqtt_flush_timer = QTimer(parent)
    parent._mqtt_flush_timer.setInterval(150)
    parent._mqtt_flush_timer.timeout.connect(parent._flush_mqtt)
    parent._mqtt_flush_timer.start()

    return page
