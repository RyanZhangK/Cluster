from typing import Any

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from .styles import C_BORDER, C_SURFACE, C_TEXT, C_TEXT_SEC


def build_topbar(parent: Any) -> QFrame:
    bar = QFrame()
    bar.setFixedHeight(60)
    bar.setStyleSheet(f"""
        QFrame {{
            background-color: {C_SURFACE};
            border-bottom: 1px solid {C_BORDER};
        }}
    """)
    row = QHBoxLayout(bar)
    row.setContentsMargins(28, 0, 28, 0)
    parent._page_title = QLabel("节点监控")
    parent._page_title.setStyleSheet(f"""
        color: {C_TEXT};
        font-size: 17px;
        font-weight: bold;
        background: transparent;
    """)
    row.addWidget(parent._page_title)
    row.addStretch()
    parent._status_label = QLabel("等待连接...")
    parent._status_label.setStyleSheet(
        f"color: {C_TEXT_SEC}; font-size: 12px; background: transparent;"
    )
    row.addWidget(parent._status_label)
    return bar
