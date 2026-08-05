from functools import partial
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    C_BG,
    C_SUCCESS,
    C_TEXT_MUTED,
    btn_style,
    combo_style,
    toggle_btn_style,
)
from .widgets import Card, add_section_label


def build_game_ctrl_page(parent: Any) -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background-color: {C_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(16)

    # 游戏模式卡
    mode_card = Card()
    ml = QVBoxLayout(mode_card)
    ml.setContentsMargins(20, 16, 20, 18)
    ml.setSpacing(12)
    add_section_label(ml, "游戏模式")
    mode_row = QHBoxLayout()
    mode_row.setSpacing(8)
    parent._mode_btns = {}
    for mode in ["征服", "占领", "爆破"]:
        btn = QPushButton(mode)
        btn.setCheckable(True)
        btn.setFixedSize(96, 38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(toggle_btn_style(mode == "征服"))
        btn.clicked.connect(partial(parent._on_mode_btn_clicked, mode))
        parent._mode_btns[mode] = btn
        mode_row.addWidget(btn)
    mode_row.addStretch()
    ml.addLayout(mode_row)
    layout.addWidget(mode_card)

    # 队伍数量卡
    team_card = Card()
    tl = QVBoxLayout(team_card)
    tl.setContentsMargins(20, 16, 20, 18)
    tl.setSpacing(12)
    add_section_label(tl, "参与队伍数")
    team_row = QHBoxLayout()
    team_row.setSpacing(8)
    parent._team_count_btns = {}
    for n in [2, 3, 4]:
        btn = QPushButton(f"{n} 队")
        btn.setCheckable(True)
        btn.setFixedSize(80, 38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(toggle_btn_style(n == 2))
        btn.clicked.connect(partial(parent._on_team_count_clicked, n))
        parent._team_count_btns[n] = btn
        team_row.addWidget(btn)
    team_row.addStretch()
    tl.addLayout(team_row)
    layout.addWidget(team_card)

    # 爆破配置卡（默认隐藏）
    parent._bomb_card = Card()
    bl = QVBoxLayout(parent._bomb_card)
    bl.setContentsMargins(20, 16, 20, 18)
    bl.setSpacing(12)
    add_section_label(bl, "爆破配置")
    bomb_row = QHBoxLayout()
    bomb_row.setSpacing(20)
    for label, attr, items in [
        ("装弹方", "_bomb_attacker_combo", ["A", "B", "C", "D"]),
        ("拆弹方", "_bomb_defender_combo", ["A", "B", "C", "D"]),
        (
            "炸弹节点",
            "_bomb_node_input",
            ["DET01", "DET02", "DET03", "DET04", "DET05", "DET06"],
        ),
    ]:
        col = QVBoxLayout()
        col.setSpacing(4)
        col_lbl = QLabel(label)
        col_lbl.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        combo = QComboBox()
        combo.addItems(items)
        combo.setFixedWidth(130)
        combo.setStyleSheet(combo_style())
        setattr(parent, attr, combo)
        col.addWidget(col_lbl)
        col.addWidget(combo)
        bomb_row.addLayout(col)
    parent._bomb_defender_combo.setCurrentText("B")
    bomb_row.addStretch()
    bl.addLayout(bomb_row)
    parent._bomb_card.setVisible(False)
    layout.addWidget(parent._bomb_card)

    # 操作按钮
    act_row = QHBoxLayout()
    act_row.setSpacing(10)
    parent._start_game_btn = QPushButton("启动游戏")
    parent._start_game_btn.setFixedSize(120, 42)
    parent._start_game_btn.setStyleSheet(btn_style(C_SUCCESS))
    parent._start_game_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._start_game_btn.clicked.connect(parent._on_start_game_clicked)
    parent._reset_game_btn = QPushButton("重置游戏")
    parent._reset_game_btn.setFixedSize(120, 42)
    parent._reset_game_btn.setStyleSheet(btn_style(C_TEXT_MUTED))
    parent._reset_game_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._reset_game_btn.clicked.connect(parent._on_reset_game_clicked)
    act_row.addWidget(parent._start_game_btn)
    act_row.addWidget(parent._reset_game_btn)
    act_row.addStretch()
    layout.addLayout(act_row)

    layout.addStretch()
    return page
