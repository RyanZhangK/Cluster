from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .styles import C_BORDER, C_DANGER, C_SIDEBAR, C_TEXT, C_TEXT_SEC
from .widgets import NavButton, SectionLabel, StatusDot


def build_sidebar(parent: Any) -> QFrame:
    sidebar = QFrame()
    sidebar.setFixedWidth(210)
    sidebar.setStyleSheet(f"""
        QFrame {{
            background-color: {C_SIDEBAR};
            border-right: 1px solid {C_BORDER};
        }}
    """)
    layout = QVBoxLayout(sidebar)
    layout.setContentsMargins(0, 0, 0, 16)
    layout.setSpacing(0)

    # Logo
    logo = QFrame()
    logo.setFixedHeight(64)
    logo.setStyleSheet(f"border-bottom: 1px solid {C_BORDER}; background: transparent;")
    logo_row = QHBoxLayout(logo)
    logo_row.setContentsMargins(18, 0, 18, 0)
    lbl = QLabel("◈  CLUSTER")
    lbl.setStyleSheet(f"""
        color: {C_TEXT};
        font-size: 15px;
        font-weight: bold;
        letter-spacing: 3px;
        background: transparent;
    """)
    logo_row.addWidget(lbl)
    layout.addWidget(logo)

    layout.addWidget(SectionLabel("监控"))
    parent._nav_nodes = NavButton("◉", "节点监控")
    parent._nav_nodes.setChecked(True)
    parent._nav_nodes.clicked.connect(lambda: parent._switch_page(0))
    layout.addWidget(parent._nav_nodes)

    layout.addWidget(SectionLabel("游戏"))
    parent._nav_game_ctrl = NavButton("◈", "游戏控制")
    parent._nav_game_ctrl.clicked.connect(lambda: parent._switch_page(1))
    layout.addWidget(parent._nav_game_ctrl)

    parent._nav_game_status = NavButton("◎", "游戏状态")
    parent._nav_game_status.clicked.connect(lambda: parent._switch_page(2))
    layout.addWidget(parent._nav_game_status)

    layout.addWidget(SectionLabel("系统"))
    parent._nav_manual = NavButton("⚡", "紧急手动")
    parent._nav_manual.clicked.connect(lambda: parent._switch_page(3))
    layout.addWidget(parent._nav_manual)

    parent._nav_frpc = NavButton("⇄", "Frpc管理")
    parent._nav_frpc.clicked.connect(lambda: parent._switch_page(4))
    layout.addWidget(parent._nav_frpc)

    parent._nav_debug = NavButton("⬡", "调试")
    parent._nav_debug.clicked.connect(lambda: parent._switch_page(5))
    layout.addWidget(parent._nav_debug)

    layout.addStretch()

    # 底部连接状态 + 关机
    bottom = QFrame()
    bottom.setStyleSheet(f"border-top: 1px solid {C_BORDER}; background: transparent;")
    bottom_col = QVBoxLayout(bottom)
    bottom_col.setContentsMargins(18, 12, 18, 12)
    bottom_col.setSpacing(8)

    conn_row = QHBoxLayout()
    parent._conn_dot = StatusDot()
    parent._conn_label = QLabel("等待连接")
    parent._conn_label.setStyleSheet(
        f"color: {C_TEXT_SEC}; font-size: 11px; background: transparent;"
    )
    conn_row.addWidget(parent._conn_dot)
    conn_row.addSpacing(6)
    conn_row.addWidget(parent._conn_label)
    conn_row.addStretch()
    bottom_col.addLayout(conn_row)

    shutdown_btn = QPushButton("关闭系统")
    shutdown_btn.setFixedHeight(34)
    shutdown_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    shutdown_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: transparent;
            color: {C_DANGER};
            border: 1px solid {C_DANGER}66;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {C_DANGER}22;
            border-color: {C_DANGER};
        }}
        QPushButton:pressed {{ background-color: {C_DANGER}44; }}
    """)
    shutdown_btn.clicked.connect(parent._on_shutdown_clicked)
    bottom_col.addWidget(shutdown_btn)

    layout.addWidget(bottom)

    return sidebar
