from functools import partial
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    C_BG,
    C_PRIMARY,
    C_TEXT,
    C_TEXT_MUTED,
    C_TEXT_SEC,
    C_WARNING,
    TEAM_COLORS,
    btn_style,
    progress_style,
)
from .widgets import Card, StatusDot, add_section_label


def build_game_status_page(parent: Any) -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background-color: {C_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(16)

    # 状态横幅
    banner = Card()
    banner_row = QHBoxLayout(banner)
    banner_row.setContentsMargins(20, 14, 20, 14)
    parent._game_state_dot = StatusDot(C_TEXT_MUTED)
    parent._game_state_label = QLabel("IDLE  ·  等待游戏开始")
    parent._game_state_label.setStyleSheet(
        f"color: {C_TEXT_SEC}; font-size: 15px; font-weight: bold; background: transparent;"
    )
    banner_row.addWidget(parent._game_state_dot)
    banner_row.addSpacing(10)
    banner_row.addWidget(parent._game_state_label)
    banner_row.addStretch()
    layout.addWidget(banner)

    # 队伍卡片
    teams_lbl = QLabel("队 伍 状 态")
    teams_lbl.setStyleSheet(
        f"color: {C_TEXT_MUTED}; font-size: 10px; font-weight: bold; letter-spacing: 2px; background: transparent;"
    )
    layout.addWidget(teams_lbl)

    teams_row = QHBoxLayout()
    teams_row.setSpacing(12)
    parent._team_cards = {}
    for team in ["A", "B", "C", "D"]:
        parent._team_cards[team] = make_team_card(team, teams_row)
    teams_row.addStretch()
    layout.addLayout(teams_row)

    # 占领进度卡（默认隐藏）
    parent._occupy_card = Card()
    ol = QVBoxLayout(parent._occupy_card)
    ol.setContentsMargins(20, 16, 20, 18)
    ol.setSpacing(10)
    add_section_label(ol, "DET 节点占领进度")
    parent._occupy_bars = {}
    for team in ["A", "B", "C", "D"]:
        row = QHBoxLayout()
        lbl = QLabel(f"队伍 {team}")
        lbl.setFixedWidth(56)
        lbl.setStyleSheet(
            f"color: {TEAM_COLORS[team]}; font-size: 12px; font-weight: bold; background: transparent;"
        )
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFixedHeight(8)
        bar.setTextVisible(False)
        bar.setStyleSheet(progress_style(TEAM_COLORS[team]))
        parent._occupy_bars[team] = bar
        row.addWidget(lbl)
        row.addWidget(bar)
        ol.addLayout(row)
    parent._occupy_card.setVisible(False)
    layout.addWidget(parent._occupy_card)

    # 爆破倒计时卡（默认隐藏）
    parent._bomb_status_card = Card()
    btl = QVBoxLayout(parent._bomb_status_card)
    btl.setContentsMargins(20, 16, 20, 20)
    btl.setSpacing(10)
    add_section_label(btl, "炸弹倒计时")
    parent._bomb_timer_label = QLabel("40")
    parent._bomb_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    parent._bomb_timer_label.setStyleSheet(
        f"color: {C_WARNING}; font-size: 56px; font-weight: bold; background: transparent;"
    )
    parent._bomb_unit_label = QLabel("秒")
    parent._bomb_unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    parent._bomb_unit_label.setStyleSheet(
        f"color: {C_TEXT_MUTED}; font-size: 14px; background: transparent;"
    )
    parent._bomb_progress = QProgressBar()
    parent._bomb_progress.setRange(0, 40)
    parent._bomb_progress.setValue(40)
    parent._bomb_progress.setFixedHeight(10)
    parent._bomb_progress.setTextVisible(False)
    parent._bomb_progress.setStyleSheet(progress_style(C_WARNING))
    btl.addWidget(parent._bomb_timer_label)
    btl.addWidget(parent._bomb_unit_label)
    btl.addWidget(parent._bomb_progress)
    parent._bomb_status_card.setVisible(False)
    layout.addWidget(parent._bomb_status_card)

    # 游戏结束操作栏（默认隐藏）
    parent._game_over_bar = QWidget()
    over_row = QHBoxLayout(parent._game_over_bar)
    over_row.setContentsMargins(0, 0, 0, 0)
    over_row.setSpacing(10)
    parent._back_to_config_btn = QPushButton("返回配置")
    parent._back_to_config_btn.setFixedSize(120, 42)
    parent._back_to_config_btn.setStyleSheet(btn_style(C_PRIMARY))
    parent._back_to_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._back_to_config_btn.clicked.connect(partial(parent._switch_page, 1))
    parent._reset_from_status_btn = QPushButton("重置游戏")
    parent._reset_from_status_btn.setFixedSize(120, 42)
    parent._reset_from_status_btn.setStyleSheet(btn_style(C_TEXT_MUTED))
    parent._reset_from_status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._reset_from_status_btn.clicked.connect(parent._on_reset_game_clicked)
    over_row.addWidget(parent._back_to_config_btn)
    over_row.addWidget(parent._reset_from_status_btn)
    over_row.addStretch()
    parent._game_over_bar.setVisible(False)
    layout.addWidget(parent._game_over_bar)

    layout.addStretch()
    return page


def make_team_card(team: str, row: QHBoxLayout) -> dict[str, Any]:
    color = TEAM_COLORS[team]
    frame = Card()
    frame.setFixedSize(150, 110)
    fl = QVBoxLayout(frame)
    fl.setContentsMargins(16, 14, 16, 14)
    fl.setSpacing(6)

    name_row = QHBoxLayout()
    dot = QLabel("●")
    dot.setStyleSheet(f"color: {color}; font-size: 16px; background: transparent;")
    name = QLabel(f"队伍 {team}")
    name.setStyleSheet(
        f"color: {C_TEXT}; font-size: 14px; font-weight: bold; background: transparent;"
    )
    name_row.addWidget(dot)
    name_row.addSpacing(4)
    name_row.addWidget(name)
    name_row.addStretch()
    fl.addLayout(name_row)

    status_lbl = QLabel("待机")
    status_lbl.setStyleSheet(
        f"color: {C_TEXT_MUTED}; font-size: 12px; background: transparent;"
    )
    fl.addWidget(status_lbl)
    fl.addStretch()

    row.addWidget(frame)
    return {"frame": frame, "status_lbl": status_lbl, "color": color}
