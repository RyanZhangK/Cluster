from functools import partial
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    C_BG,
    C_BORDER,
    C_CARD,
    C_PRIMARY,
    C_SURFACE,
    C_TEXT,
    C_WARNING,
    btn_style,
)
from .widgets import Card, add_section_label


def build_manual_page(parent: Any) -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background-color: {C_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(16)

    warn_card = Card()
    warn_card.setStyleSheet(f"""
        QFrame {{
            background-color: {C_WARNING}18;
            border: 1px solid {C_WARNING}55;
            border-radius: 8px;
        }}
    """)
    warn_row = QHBoxLayout(warn_card)
    warn_row.setContentsMargins(16, 12, 16, 12)
    warn_lbl = QLabel(
        "\u26a0  紧急手动模式 — 点击任意按钮将立即中断当前音效队列并播放所选音效"
    )
    warn_lbl.setStyleSheet(
        f"color: {C_WARNING}; font-size: 12px; background: transparent;"
    )
    warn_row.addWidget(warn_lbl)
    layout.addWidget(warn_card)

    # 按音效分组，每组一张卡
    groups = [
        (
            "系统",
            [
                ("sys_online", "系统上线"),
                ("sys_offline", "系统下线"),
                ("game_started", "游戏开始"),
                ("game_stopped", "游戏结束"),
            ],
        ),
        (
            "队伍就绪",
            [
                ("activated_A", "A 队就绪"),
                ("activated_B", "B 队就绪"),
                ("activated_C", "C 队就绪"),
                ("activated_D", "D 队就绪"),
            ],
        ),
        (
            "队伍淘汰",
            [
                ("eliminated_A", "A 队淘汰"),
                ("eliminated_B", "B 队淘汰"),
                ("eliminated_C", "C 队淘汰"),
                ("eliminated_D", "D 队淘汰"),
            ],
        ),
        (
            "队伍胜利",
            [
                ("victory_A", "A 队胜利"),
                ("victory_B", "B 队胜利"),
                ("victory_C", "C 队胜利"),
                ("victory_D", "D 队胜利"),
                ("victory_T", "T 队胜利"),
                ("victory_CT", "CT 队胜利"),
            ],
        ),
        (
            "DET 热点占领",
            [
                ("hotpoint_A", "A 队占领"),
                ("hotpoint_B", "B 队占领"),
                ("hotpoint_C", "C 队占领"),
                ("hotpoint_D", "D 队占领"),
            ],
        ),
        (
            "炸弹",
            [
                ("bomb_activated", "炸弹激活"),
                ("bomb_defused", "炸弹拆除"),
            ],
        ),
    ]

    for group_name, items in groups:
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 20, 16)
        cl.setSpacing(10)
        add_section_label(cl, group_name)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for key, label in items:
            btn = QPushButton(label)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style(C_CARD).replace(C_CARD, C_SURFACE))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C_SURFACE};
                    color: {C_TEXT};
                    border: 1px solid {C_BORDER};
                    border-radius: 6px;
                    padding: 4px 14px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {C_CARD};
                    border-color: {C_PRIMARY};
                    color: {C_TEXT};
                }}
                QPushButton:pressed {{ background-color: {C_PRIMARY}44; }}
            """)
            btn.clicked.connect(partial(parent._on_manual_play, key))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        cl.addLayout(btn_row)
        layout.addWidget(card)

    layout.addStretch()
    return page
