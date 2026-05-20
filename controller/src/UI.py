import json
import logging
import tomllib
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from audio_player import AudioPlayer
from event_bus import EventBus
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import FRPC_AUTH_TOKEN, FRPC_PROXIES, FRPC_SERVER_ADDR, FRPC_SERVER_PORT
from .node_manager import NodeManager, OnlineStatus

if TYPE_CHECKING:
    from frpc_manager import FrpcManager
    from game_manager import GameManager
    from node_manager import NodeState

logger = logging.getLogger(__name__)

# ─── 色彩系统 ─────────────────────────────────────────────────────────────────
C_BG = "#0f1117"
C_SURFACE = "#161b27"
C_CARD = "#1e2435"
C_BORDER = "#2a3045"
C_PRIMARY = "#4f6ef7"
C_PRIMARY_H = "#6b84f8"
C_SUCCESS = "#22c55e"
C_DANGER = "#ef4444"
C_WARNING = "#f59e0b"
C_TEXT = "#e2e8f0"
C_TEXT_SEC = "#8b95b0"
C_TEXT_MUTED = "#4a5270"
C_SIDEBAR = "#0c0f1a"
C_NAV_HOVER = "#181d2e"
C_NAV_ACTIVE = "#1e2a4a"

TEAM_COLORS = {"A": "#ef4444", "B": "#3b82f6", "C": "#22c55e", "D": "#f59e0b"}


# ─── 复用组件 ─────────────────────────────────────────────────────────────────


class NavButton(QPushButton):
    def __init__(
        self, icon_text: str, label: str, parent: "QWidget | None" = None
    ) -> None:
        super().__init__(parent)
        self._icon_text = icon_text
        self._label = label
        self.setText(f"  {icon_text}  {label}")
        self.setCheckable(True)
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh()

    def setChecked(self, arg__1: bool) -> None:
        super().setChecked(arg__1)
        self._refresh()

    def _refresh(self) -> None:
        checked = self.isChecked()
        left = (
            f"border-left: 3px solid {C_PRIMARY};"
            if checked
            else "border-left: 3px solid transparent;"
        )
        bg = C_NAV_ACTIVE if checked else "transparent"
        color = C_TEXT if checked else C_TEXT_SEC
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: none;
                {left}
                padding: 0 18px;
                text-align: left;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {C_NAV_HOVER};
                color: {C_TEXT};
            }}
        """)


class StatusDot(QLabel):
    def __init__(
        self, color: str = C_TEXT_MUTED, parent: "QLabel | None" = None
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._set(color)

    def set_color(self, color: str) -> None:
        self._set(color)

    def _set(self, color: str) -> None:
        self.setStyleSheet(f"background-color: {color}; border-radius: 4px;")


class Card(QFrame):
    def __init__(self, parent: "QFrame | None" = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {C_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)


class SectionLabel(QLabel):
    def __init__(self, text: str, parent: "QLabel | None" = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            color: {C_TEXT_MUTED};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            padding: 14px 18px 4px 18px;
            background: transparent;
        """)


# ─── 主窗口 ───────────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    COL_NODE_ID = 0
    COL_TYPE = 1
    COL_STATUS = 2
    COL_TEAM = 3
    COL_HEARTBEAT = 4
    COLUMN_HEADERS = ["节点ID", "类型", "在线状态", "激活队伍", "最后心跳"]

    def __init__(
        self,
        node_manager: "NodeManager",
        event_bus: "EventBus",
        audio_player: "AudioPlayer",
        frpc_manager: "FrpcManager | None" = None,
        parent: "QMainWindow | None" = None,
    ) -> None:
        super().__init__(parent)
        self._node_manager = node_manager
        self._event_bus = event_bus
        self._audio_player = audio_player
        self._frpc_manager: "FrpcManager | None" = frpc_manager
        self._game_manager: "GameManager | None" = None
        self._current_mode = "征服"
        self._current_team_count = 2
        self._current_participating_teams: list[str] = []
        self._node_to_row: dict[str, int] = {}

        self._bomb_attacker_combo = QComboBox()
        self._bomb_defender_combo = QComboBox()
        self._bomb_node_input = QComboBox()

        self.setWindowTitle("Cluster 节点管理系统")
        self.setGeometry(100, 100, 1320, 800)
        self.setMinimumSize(1024, 640)

        self._setup_ui()
        self._setup_table()
        self._connect_signals()

    # ── 布局骨架 ───────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QWidget()
        root.setStyleSheet(
            f"background-color: {C_BG}; font-family: 'Segoe UI', 'Arial', sans-serif;"
        )
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        content = QFrame()
        content.setStyleSheet(f"background-color: {C_BG};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._build_topbar())

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {C_BG};")
        self._stack.addWidget(self._build_node_page())
        self._stack.addWidget(self._build_game_ctrl_page())
        self._stack.addWidget(self._build_game_status_page())
        self._stack.addWidget(self._build_manual_page())
        self._stack.addWidget(self._build_frpc_page())
        content_layout.addWidget(self._stack)

        root_layout.addWidget(content, 1)

        self._nav_buttons = [
            self._nav_nodes,
            self._nav_game_ctrl,
            self._nav_game_status,
            self._nav_manual,
            self._nav_frpc,
        ]
        self._page_titles = [
            "节点监控",
            "游戏控制",
            "游戏状态",
            "紧急手动",
            "Frpc管理",
        ]

    def _build_sidebar(self) -> QFrame:
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
        logo.setStyleSheet(
            f"border-bottom: 1px solid {C_BORDER}; background: transparent;"
        )
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
        self._nav_nodes = NavButton("◉", "节点监控")
        self._nav_nodes.setChecked(True)
        self._nav_nodes.clicked.connect(lambda: self._switch_page(0))
        layout.addWidget(self._nav_nodes)

        layout.addWidget(SectionLabel("游戏"))
        self._nav_game_ctrl = NavButton("◈", "游戏控制")
        self._nav_game_ctrl.clicked.connect(lambda: self._switch_page(1))
        layout.addWidget(self._nav_game_ctrl)

        self._nav_game_status = NavButton("◎", "游戏状态")
        self._nav_game_status.clicked.connect(lambda: self._switch_page(2))
        layout.addWidget(self._nav_game_status)

        layout.addWidget(SectionLabel("系统"))
        self._nav_manual = NavButton("⚡", "紧急手动")
        self._nav_manual.clicked.connect(lambda: self._switch_page(3))
        layout.addWidget(self._nav_manual)

        self._nav_frpc = NavButton("⇄", "Frpc管理")
        self._nav_frpc.clicked.connect(lambda: self._switch_page(4))
        layout.addWidget(self._nav_frpc)

        layout.addStretch()

        # 底部连接状态 + 关机
        bottom = QFrame()
        bottom.setStyleSheet(
            f"border-top: 1px solid {C_BORDER}; background: transparent;"
        )
        bottom_col = QVBoxLayout(bottom)
        bottom_col.setContentsMargins(18, 12, 18, 12)
        bottom_col.setSpacing(8)

        conn_row = QHBoxLayout()
        self._conn_dot = StatusDot()
        self._conn_label = QLabel("等待连接")
        self._conn_label.setStyleSheet(
            f"color: {C_TEXT_SEC}; font-size: 11px; background: transparent;"
        )
        conn_row.addWidget(self._conn_dot)
        conn_row.addSpacing(6)
        conn_row.addWidget(self._conn_label)
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
        shutdown_btn.clicked.connect(self._on_shutdown_clicked)
        bottom_col.addWidget(shutdown_btn)

        layout.addWidget(bottom)

        return sidebar

    def _build_topbar(self) -> QFrame:
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
        self._page_title = QLabel("节点监控")
        self._page_title.setStyleSheet(f"""
            color: {C_TEXT};
            font-size: 17px;
            font-weight: bold;
            background: transparent;
        """)
        row.addWidget(self._page_title)
        row.addStretch()
        self._status_label = QLabel("等待连接...")
        self._status_label.setStyleSheet(
            f"color: {C_TEXT_SEC}; font-size: 12px; background: transparent;"
        )
        row.addWidget(self._status_label)
        return bar

    # ── 节点监控页 ─────────────────────────────────────────────────────────────

    def _build_node_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {C_BG};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # 统计卡片行
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._stat_val_total = self._stat_card(stats_row, "总节点", "0", C_PRIMARY)
        self._stat_val_online = self._stat_card(stats_row, "在线", "0", C_SUCCESS)
        self._stat_val_offline = self._stat_card(stats_row, "离线", "0", C_DANGER)
        stats_row.addStretch()
        layout.addLayout(stats_row)

        # 操作行
        act_row = QHBoxLayout()
        self._reset_btn = QPushButton("重置选中节点")
        self._reset_btn.setFixedHeight(36)
        self._reset_btn.setStyleSheet(self._btn_style(C_PRIMARY))
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self._on_reset_btn_clicked)
        act_row.addWidget(self._reset_btn)
        act_row.addStretch()
        layout.addLayout(act_row)

        # 表格
        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMN_HEADERS))
        self._table.setHorizontalHeaderLabels(self.COLUMN_HEADERS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setStyleSheet(self._table_style())
        layout.addWidget(self._table)

        return page

    def _stat_card(
        self, parent_layout: QHBoxLayout, label: str, value: str, color: str
    ) -> QLabel:
        card = Card()
        card.setFixedSize(130, 76)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 10, 16, 10)
        cl.setSpacing(2)
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            f"color: {color}; font-size: 26px; font-weight: bold; background: transparent;"
        )
        txt_lbl = QLabel(label)
        txt_lbl.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        cl.addWidget(val_lbl)
        cl.addWidget(txt_lbl)
        parent_layout.addWidget(card)
        return val_lbl

    def _update_stats(self) -> None:
        nodes = self._node_manager.get_all_nodes()
        total = len(nodes)
        online = sum(1 for s in nodes.values() if s.status == OnlineStatus.ONLINE)
        self._stat_val_total.setText(str(total))
        self._stat_val_online.setText(str(online))
        self._stat_val_offline.setText(str(total - online))

    # ── 游戏控制页 ─────────────────────────────────────────────────────────────

    def _build_game_ctrl_page(self) -> QWidget:
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
        self._card_section_label(ml, "游戏模式")
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_btns: dict[str, QPushButton] = {}
        for mode in ["征服", "占领", "爆破"]:
            btn = QPushButton(mode)
            btn.setCheckable(True)
            btn.setFixedSize(96, 38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._toggle_btn_style(mode == "征服"))
            btn.clicked.connect(partial(self._on_mode_btn_clicked, mode))
            self._mode_btns[mode] = btn
            mode_row.addWidget(btn)
        mode_row.addStretch()
        ml.addLayout(mode_row)
        layout.addWidget(mode_card)

        # 队伍数量卡
        team_card = Card()
        tl = QVBoxLayout(team_card)
        tl.setContentsMargins(20, 16, 20, 18)
        tl.setSpacing(12)
        self._card_section_label(tl, "参与队伍数")
        team_row = QHBoxLayout()
        team_row.setSpacing(8)
        self._team_count_btns: dict[int, QPushButton] = {}
        for n in [2, 3, 4]:
            btn = QPushButton(f"{n} 队")
            btn.setCheckable(True)
            btn.setFixedSize(80, 38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._toggle_btn_style(n == 2))
            btn.clicked.connect(partial(self._on_team_count_clicked, n))
            self._team_count_btns[n] = btn
            team_row.addWidget(btn)
        team_row.addStretch()
        tl.addLayout(team_row)
        layout.addWidget(team_card)

        # 爆破配置卡（默认隐藏）
        self._bomb_card = Card()
        bl = QVBoxLayout(self._bomb_card)
        bl.setContentsMargins(20, 16, 20, 18)
        bl.setSpacing(12)
        self._card_section_label(bl, "爆破配置")
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
            combo.setStyleSheet(self._combo_style())
            setattr(self, attr, combo)
            col.addWidget(col_lbl)
            col.addWidget(combo)
            bomb_row.addLayout(col)
        self._bomb_defender_combo.setCurrentText("B")
        bomb_row.addStretch()
        bl.addLayout(bomb_row)
        self._bomb_card.setVisible(False)
        layout.addWidget(self._bomb_card)

        # 操作按钮
        act_row = QHBoxLayout()
        act_row.setSpacing(10)
        self._start_game_btn = QPushButton("启动游戏")
        self._start_game_btn.setFixedSize(120, 42)
        self._start_game_btn.setStyleSheet(self._btn_style(C_SUCCESS))
        self._start_game_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_game_btn.clicked.connect(self._on_start_game_clicked)
        self._reset_game_btn = QPushButton("重置游戏")
        self._reset_game_btn.setFixedSize(120, 42)
        self._reset_game_btn.setStyleSheet(self._btn_style(C_TEXT_MUTED))
        self._reset_game_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_game_btn.clicked.connect(self._on_reset_game_clicked)
        act_row.addWidget(self._start_game_btn)
        act_row.addWidget(self._reset_game_btn)
        act_row.addStretch()
        layout.addLayout(act_row)

        layout.addStretch()
        return page

    def _on_mode_btn_clicked(self, mode: str) -> None:
        self._current_mode = mode
        for m, btn in self._mode_btns.items():
            btn.setChecked(m == mode)
            btn.setStyleSheet(self._toggle_btn_style(m == mode))
        self._bomb_card.setVisible(mode == "爆破")

    def _on_team_count_clicked(self, count: int) -> None:
        self._current_team_count = count
        for n, btn in self._team_count_btns.items():
            btn.setChecked(n == count)
            btn.setStyleSheet(self._toggle_btn_style(n == count))

    # ── 游戏状态页 ─────────────────────────────────────────────────────────────

    def _build_game_status_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {C_BG};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # 状态横幅
        banner = Card()
        banner_row = QHBoxLayout(banner)
        banner_row.setContentsMargins(20, 14, 20, 14)
        self._game_state_dot = StatusDot(C_TEXT_MUTED)
        self._game_state_label = QLabel("IDLE  ·  等待游戏开始")
        self._game_state_label.setStyleSheet(
            f"color: {C_TEXT_SEC}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        banner_row.addWidget(self._game_state_dot)
        banner_row.addSpacing(10)
        banner_row.addWidget(self._game_state_label)
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
        self._team_cards: dict[str, dict[Any, Any]] = {}
        for team in ["A", "B", "C", "D"]:
            self._team_cards[team] = self._make_team_card(team, teams_row)
        teams_row.addStretch()
        layout.addLayout(teams_row)

        # 占领进度卡（默认隐藏）
        self._occupy_card = Card()
        ol = QVBoxLayout(self._occupy_card)
        ol.setContentsMargins(20, 16, 20, 18)
        ol.setSpacing(10)
        self._card_section_label(ol, "DET 节点占领进度")
        self._occupy_bars: dict[str, QProgressBar] = {}
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
            bar.setStyleSheet(self._progress_style(TEAM_COLORS[team]))
            self._occupy_bars[team] = bar
            row.addWidget(lbl)
            row.addWidget(bar)
            ol.addLayout(row)
        self._occupy_card.setVisible(False)
        layout.addWidget(self._occupy_card)

        # 爆破倒计时卡（默认隐藏）
        self._bomb_status_card = Card()
        btl = QVBoxLayout(self._bomb_status_card)
        btl.setContentsMargins(20, 16, 20, 20)
        btl.setSpacing(10)
        self._card_section_label(btl, "炸弹倒计时")
        self._bomb_timer_label = QLabel("40")
        self._bomb_timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bomb_timer_label.setStyleSheet(
            f"color: {C_WARNING}; font-size: 56px; font-weight: bold; background: transparent;"
        )
        self._bomb_unit_label = QLabel("秒")
        self._bomb_unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bomb_unit_label.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        self._bomb_progress = QProgressBar()
        self._bomb_progress.setRange(0, 40)
        self._bomb_progress.setValue(40)
        self._bomb_progress.setFixedHeight(10)
        self._bomb_progress.setTextVisible(False)
        self._bomb_progress.setStyleSheet(self._progress_style(C_WARNING))
        btl.addWidget(self._bomb_timer_label)
        btl.addWidget(self._bomb_unit_label)
        btl.addWidget(self._bomb_progress)
        self._bomb_status_card.setVisible(False)
        layout.addWidget(self._bomb_status_card)

        # 游戏结束操作栏（默认隐藏）
        self._game_over_bar = QWidget()
        over_row = QHBoxLayout(self._game_over_bar)
        over_row.setContentsMargins(0, 0, 0, 0)
        over_row.setSpacing(10)
        self._back_to_config_btn = QPushButton("返回配置")
        self._back_to_config_btn.setFixedSize(120, 42)
        self._back_to_config_btn.setStyleSheet(self._btn_style(C_PRIMARY))
        self._back_to_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_to_config_btn.clicked.connect(lambda: self._switch_page(1))
        self._reset_from_status_btn = QPushButton("重置游戏")
        self._reset_from_status_btn.setFixedSize(120, 42)
        self._reset_from_status_btn.setStyleSheet(self._btn_style(C_TEXT_MUTED))
        self._reset_from_status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_from_status_btn.clicked.connect(self._on_reset_game_clicked)
        over_row.addWidget(self._back_to_config_btn)
        over_row.addWidget(self._reset_from_status_btn)
        over_row.addStretch()
        self._game_over_bar.setVisible(False)
        layout.addWidget(self._game_over_bar)

        layout.addStretch()
        return page

    def _build_manual_page(self) -> QWidget:
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
            "⚠  紧急手动模式 — 点击任意按钮将立即中断当前音效队列并播放所选音效"
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
            self._card_section_label(cl, group_name)
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            for key, label in items:
                btn = QPushButton(label)
                btn.setFixedHeight(34)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(self._btn_style(C_CARD).replace(C_CARD, C_SURFACE))
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
                btn.clicked.connect(partial(self._on_manual_play, key))
                btn_row.addWidget(btn)
            btn_row.addStretch()
            cl.addLayout(btn_row)
            layout.addWidget(card)

        layout.addStretch()
        return page

    def _on_manual_play(self, key: str) -> None:
        self._audio_player._queue.clear()  # pyright: ignore[reportPrivateUsage]
        self._audio_player._current = None  # pyright: ignore[reportPrivateUsage]
        self._audio_player._play(key)  # pyright: ignore[reportPrivateUsage]

    # ── Frpc 管理页 ─────────────────────────────────────────────────────────────

    def _build_frpc_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {C_BG};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # 状态卡片
        status_card = Card()
        sc_layout = QVBoxLayout(status_card)
        sc_layout.setContentsMargins(20, 16, 20, 18)
        sc_layout.setSpacing(12)

        status_row = QHBoxLayout()
        self._frpc_status_dot = StatusDot(C_TEXT_MUTED)
        self._frpc_status_label = QLabel("FRPC 已停止")
        self._frpc_status_label.setStyleSheet(
            f"color: {C_TEXT_SEC}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        status_row.addWidget(self._frpc_status_dot)
        status_row.addSpacing(10)
        status_row.addWidget(self._frpc_status_label)
        status_row.addStretch()
        sc_layout.addLayout(status_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._frpc_start_btn = QPushButton("启动")
        self._frpc_start_btn.setFixedSize(100, 38)
        self._frpc_start_btn.setStyleSheet(self._btn_style(C_SUCCESS))
        self._frpc_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._frpc_start_btn.clicked.connect(self._on_frpc_start)
        self._frpc_stop_btn = QPushButton("停止")
        self._frpc_stop_btn.setFixedSize(100, 38)
        self._frpc_stop_btn.setStyleSheet(self._btn_style(C_DANGER))
        self._frpc_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._frpc_stop_btn.clicked.connect(self._on_frpc_stop)
        self._frpc_stop_btn.setEnabled(False)
        btn_row.addWidget(self._frpc_start_btn)
        btn_row.addWidget(self._frpc_stop_btn)
        btn_row.addStretch()
        sc_layout.addLayout(btn_row)
        layout.addWidget(status_card)

        # 服务器配置卡
        server_card = Card()
        svl = QVBoxLayout(server_card)
        svl.setContentsMargins(20, 16, 20, 18)
        svl.setSpacing(12)
        self._card_section_label(svl, "服务器配置")

        form_grid = QVBoxLayout()
        form_grid.setSpacing(8)

        for label, widget in [
            ("服务器地址", "_frpc_server_addr"),
            ("认证令牌", "_frpc_auth_token"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(label)
            lbl.setFixedWidth(72)
            lbl.setStyleSheet(
                f"color: {C_TEXT_SEC}; font-size: 12px; background: transparent;"
            )
            edit = QLineEdit()
            edit.setStyleSheet(self._input_style())
            setattr(self, widget, edit)
            row.addWidget(lbl)
            row.addWidget(edit)
            form_grid.addLayout(row)

        port_row = QHBoxLayout()
        port_row.setSpacing(12)
        port_lbl = QLabel("服务器端口")
        port_lbl.setFixedWidth(72)
        port_lbl.setStyleSheet(
            f"color: {C_TEXT_SEC}; font-size: 12px; background: transparent;"
        )
        self._frpc_server_port = QSpinBox()
        self._frpc_server_port.setRange(1, 65535)
        self._frpc_server_port.setValue(7000)
        self._frpc_server_port.setStyleSheet(self._spinbox_style())
        port_row.addWidget(port_lbl)
        port_row.addWidget(self._frpc_server_port)
        port_row.addStretch()
        form_grid.addLayout(port_row)

        svl.addLayout(form_grid)
        layout.addWidget(server_card)

        # 代理列表卡
        proxy_card = Card()
        pvl = QVBoxLayout(proxy_card)
        pvl.setContentsMargins(20, 16, 20, 18)
        pvl.setSpacing(12)
        self._card_section_label(pvl, "代理列表")

        # 代理表格
        self._proxy_table = QTableWidget()
        self._proxy_table.setColumnCount(5)
        self._proxy_table.setHorizontalHeaderLabels(
            ["名称", "类型", "本地地址", "本地端口", "远程端口"]
        )
        self._proxy_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._proxy_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._proxy_table.setStyleSheet(self._table_style())
        self._proxy_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._proxy_table.setShowGrid(False)
        self._proxy_table.verticalHeader().setVisible(False)
        self._proxy_table.setMaximumHeight(200)
        pvl.addWidget(self._proxy_table)

        # 添加代理表单
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self._proxy_name_input = QLineEdit()
        self._proxy_name_input.setPlaceholderText("名称")
        self._proxy_name_input.setStyleSheet(self._input_style())
        self._proxy_type_combo = QComboBox()
        self._proxy_type_combo.addItems(["tcp", "udp"])
        self._proxy_type_combo.setStyleSheet(self._combo_style())
        self._proxy_type_combo.setFixedWidth(80)
        self._proxy_local_ip = QLineEdit()
        self._proxy_local_ip.setPlaceholderText("127.0.0.1")
        self._proxy_local_ip.setStyleSheet(self._input_style())
        self._proxy_local_port = QSpinBox()
        self._proxy_local_port.setRange(1, 65535)
        self._proxy_local_port.setValue(80)
        self._proxy_local_port.setStyleSheet(self._spinbox_style())
        self._proxy_remote_port = QSpinBox()
        self._proxy_remote_port.setRange(1, 65535)
        self._proxy_remote_port.setValue(8080)
        self._proxy_remote_port.setStyleSheet(self._spinbox_style())
        add_row.addWidget(self._proxy_name_input)
        add_row.addWidget(self._proxy_type_combo)
        add_row.addWidget(self._proxy_local_ip)
        add_row.addWidget(self._proxy_local_port)
        add_row.addWidget(self._proxy_remote_port)
        pvl.addLayout(add_row)

        proxy_btn_row = QHBoxLayout()
        proxy_btn_row.setSpacing(10)
        add_proxy_btn = QPushButton("+ 添加代理")
        add_proxy_btn.setFixedHeight(34)
        add_proxy_btn.setStyleSheet(self._btn_style(C_PRIMARY))
        add_proxy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_proxy_btn.clicked.connect(self._on_add_proxy)
        del_proxy_btn = QPushButton("删除选中")
        del_proxy_btn.setFixedHeight(34)
        del_proxy_btn.setStyleSheet(self._btn_style(C_TEXT_MUTED))
        del_proxy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_proxy_btn.clicked.connect(self._on_delete_proxy)
        proxy_btn_row.addWidget(add_proxy_btn)
        proxy_btn_row.addWidget(del_proxy_btn)
        proxy_btn_row.addStretch()
        pvl.addLayout(proxy_btn_row)

        layout.addWidget(proxy_card)

        # 日志输出卡
        log_card = Card()
        ll = QVBoxLayout(log_card)
        ll.setContentsMargins(20, 16, 20, 18)
        ll.setSpacing(10)
        self._card_section_label(ll, "日志输出")

        self._frpc_log = QTextEdit()
        self._frpc_log.setReadOnly(True)
        self._frpc_log.setFont(QFont("Consolas, monospace", 9))
        self._frpc_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C_SIDEBAR};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
            }}
            QScrollBar:vertical {{
                background: {C_BG};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER};
                border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        ll.addWidget(self._frpc_log)

        clear_btn_row = QHBoxLayout()
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.setFixedHeight(34)
        clear_log_btn.setStyleSheet(self._btn_style(C_TEXT_MUTED))
        clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_log_btn.clicked.connect(self._frpc_log.clear)
        clear_btn_row.addWidget(clear_log_btn)
        clear_btn_row.addStretch()
        ll.addLayout(clear_btn_row)

        layout.addWidget(log_card, 1)

        # 加载已保存的配置
        self._load_frpc_config()
        return page

    def _load_frpc_config(self) -> None:
        """从上次生成的 frpc.toml 恢复配置，fallback 到 pydantic settings。"""
        frpc_toml = Path(__file__).parent.parent / "frpc.toml"
        if frpc_toml.exists():
            try:
                data = tomllib.loads(frpc_toml.read_text(encoding="utf-8"))
                self._frpc_server_addr.setText(data.get("serverAddr", ""))
                self._frpc_server_port.setValue(
                    data.get("serverPort", FRPC_SERVER_PORT)
                )
                auth = data.get("auth", {})
                if isinstance(auth, dict):
                    self._frpc_auth_token.setText(auth.get("token", ""))
                proxies = data.get("proxies", FRPC_PROXIES)
                if isinstance(proxies, str):
                    proxies = json.loads(proxies)
                self._populate_proxy_table(proxies)
                return
            except (tomllib.TOMLDecodeError, OSError):
                pass

        self._frpc_server_addr.setText(FRPC_SERVER_ADDR)
        self._frpc_server_port.setValue(FRPC_SERVER_PORT)
        self._frpc_auth_token.setText(FRPC_AUTH_TOKEN)
        try:
            proxies = json.loads(FRPC_PROXIES)
        except (json.JSONDecodeError, TypeError):
            proxies = []
        self._populate_proxy_table(proxies)

    def _collect_frpc_config(self) -> dict:
        """从 UI 表单收集 frpc 配置。"""
        proxies = []
        for row in range(self._proxy_table.rowCount()):
            name = self._proxy_table.item(row, 0)
            ptype = self._proxy_table.item(row, 1)
            lip = self._proxy_table.item(row, 2)
            lport = self._proxy_table.item(row, 3)
            rport = self._proxy_table.item(row, 4)
            if name and ptype and lip and lport and rport:
                proxies.append(
                    {
                        "name": name.text(),
                        "type": ptype.text(),
                        "local_ip": lip.text(),
                        "local_port": int(lport.text()),
                        "remote_port": int(rport.text()),
                    }
                )
        return {
            "server_addr": self._frpc_server_addr.text(),
            "server_port": self._frpc_server_port.value(),
            "auth_token": self._frpc_auth_token.text(),
            "proxies": proxies,
        }

    def _populate_proxy_table(self, proxies: list) -> None:
        """将代理列表填充到表格。"""
        self._proxy_table.setRowCount(0)
        for row, p in enumerate(proxies):
            self._proxy_table.insertRow(row)
            for col, key in enumerate(
                ["name", "type", "local_ip", "local_port", "remote_port"]
            ):
                val = str(p.get(key, ""))
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setForeground(QColor(C_TEXT))
                self._proxy_table.setItem(row, col, item)
            self._proxy_table.setRowHeight(row, 32)

    @Slot()
    def _on_frpc_start(self) -> None:
        if self._frpc_manager is None:
            return
        config = self._collect_frpc_config()
        self._frpc_manager.start(config)

    @Slot()
    def _on_frpc_stop(self) -> None:
        if self._frpc_manager is None:
            return
        self._frpc_manager.stop()

    @Slot()
    def _on_add_proxy(self) -> None:
        name = self._proxy_name_input.text().strip()
        if not name:
            return
        row = self._proxy_table.rowCount()
        self._proxy_table.insertRow(row)
        data = [
            name,
            self._proxy_type_combo.currentText(),
            self._proxy_local_ip.text().strip() or "127.0.0.1",
            str(self._proxy_local_port.value()),
            str(self._proxy_remote_port.value()),
        ]
        for col, val in enumerate(data):
            item = QTableWidgetItem(val)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(QColor(C_TEXT))
            self._proxy_table.setItem(row, col, item)
        self._proxy_table.setRowHeight(row, 32)
        self._proxy_name_input.clear()

    @Slot()
    def _on_delete_proxy(self) -> None:
        selected = self._proxy_table.selectedIndexes()
        if not selected:
            return
        self._proxy_table.removeRow(selected[0].row())

    @Slot(bool)
    def _on_frpc_status_changed(self, running: bool) -> None:
        if running:
            self._frpc_status_dot.set_color(C_SUCCESS)
            self._frpc_status_label.setText("FRPC 运行中")
            self._frpc_status_label.setStyleSheet(
                f"color: {C_SUCCESS}; font-size: 15px; font-weight: bold; background: transparent;"
            )
            self._frpc_start_btn.setEnabled(False)
            self._frpc_stop_btn.setEnabled(True)
        else:
            self._frpc_status_dot.set_color(C_TEXT_MUTED)
            self._frpc_status_label.setText("FRPC 已停止")
            self._frpc_status_label.setStyleSheet(
                f"color: {C_TEXT_SEC}; font-size: 15px; font-weight: bold; background: transparent;"
            )
            self._frpc_start_btn.setEnabled(True)
            self._frpc_stop_btn.setEnabled(False)

    @Slot(str)
    def _on_frpc_log_received(self, text: str) -> None:
        self._frpc_log.append(text)
        # 自动滚动到底部
        scrollbar = self._frpc_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def _on_shutdown_clicked(self) -> None:

        self._audio_player._queue.clear()  # pyright: ignore[reportPrivateUsage]
        self._audio_player.play_sys_offline()
        # 等音效播完再退出：监听 playing 结束
        # self.__shutdown_pending = True
        self._audio_player._effects  # 确保已加载  # pyright: ignore[reportPrivateUsage]
        # 用单次定时器轮询，避免在音效结束前退出
        from PySide6.QtCore import QTimer

        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(200)
        self._shutdown_timer.timeout.connect(self._check_shutdown)
        self._shutdown_timer.start()

    def _check_shutdown(self) -> None:
        if (
            self._audio_player._current is None  # pyright: ignore[reportPrivateUsage]
            and not self._audio_player._queue  # pyright: ignore[reportPrivateUsage]
        ):
            self._shutdown_timer.stop()
            from PySide6.QtWidgets import QApplication

            QApplication.quit()

    def _make_team_card(self, team: str, row: QHBoxLayout) -> dict[str, Any]:
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

    def _update_team_card(
        self, team: str, status_text: str, eliminated: bool = False
    ) -> None:
        if team not in self._team_cards:
            return
        d = self._team_cards[team]
        lbl: QLabel = d["status_lbl"]
        if eliminated:
            lbl.setText("已淘汰")
            lbl.setStyleSheet(
                f"color: {C_DANGER}; font-size: 12px; background: transparent;"
            )
            d["frame"].setStyleSheet(f"""
                QFrame {{
                    background-color: {C_CARD};
                    border: 1px solid {C_DANGER}55;
                    border-radius: 8px;
                }}
            """)
        else:
            lbl.setText(status_text)
            lbl.setStyleSheet(
                f"color: {d['color']}; font-size: 12px; background: transparent;"
            )
            d["frame"].setStyleSheet(f"""
                QFrame {{
                    background-color: {C_CARD};
                    border: 1px solid {C_BORDER};
                    border-radius: 8px;
                }}
            """)

    def _update_occupy_bars(self) -> None:
        if not self._game_manager:
            return
        nodes = self._node_manager.get_all_nodes()
        online_det = sum(
            1
            for nid, s in nodes.items()
            if nid.startswith("DET") and s.status == OnlineStatus.ONLINE
        )
        if online_det == 0:
            return
        det_map: dict[str, str] = getattr(self._game_manager, "_det_activation", {})
        team_counts: dict[str, int] = {}
        for team in det_map.values():
            team_counts[team] = team_counts.get(team, 0) + 1
        for team, bar in self._occupy_bars.items():
            pct = int(team_counts.get(team, 0) / online_det * 100)
            bar.setValue(pct)

    # ── 样式工厂 ───────────────────────────────────────────────────────────────

    def _card_section_label(self, layout: QVBoxLayout, text: str) -> None:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 10px; font-weight: bold; letter-spacing: 1px; background: transparent;"
        )
        layout.addWidget(lbl)

    def _btn_style(self, bg: str) -> str:
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {C_TEXT};
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {bg}cc; }}
            QPushButton:pressed {{ background-color: {bg}99; }}
            QPushButton:disabled {{
                background-color: {C_BORDER};
                color: {C_TEXT_MUTED};
            }}
        """

    def _toggle_btn_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background-color: {C_PRIMARY};
                    color: {C_TEXT};
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {C_PRIMARY_H}; }}
            """
        return f"""
            QPushButton {{
                background-color: {C_SURFACE};
                color: {C_TEXT_SEC};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {C_CARD};
                color: {C_TEXT};
                border-color: {C_PRIMARY}88;
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background-color: {C_SURFACE};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QComboBox:hover {{ border-color: {C_PRIMARY}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: {C_CARD};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                selection-background-color: {C_PRIMARY};
            }}
        """

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {C_SURFACE};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {C_PRIMARY}; }}
            QLineEdit::placeholder {{ color: {C_TEXT_MUTED}; }}
        """

    def _spinbox_style(self) -> str:
        return f"""
            QSpinBox {{
                background-color: {C_SURFACE};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QSpinBox:focus {{ border-color: {C_PRIMARY}; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: {C_CARD};
                border: none;
                width: 16px;
            }}
            QSpinBox::up-arrow {{
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid {C_TEXT};
            }}
            QSpinBox::down-arrow {{
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {C_TEXT};
            }}
        """

    def _table_style(self) -> str:
        return f"""
            QTableWidget {{
                background-color: {C_SURFACE};
                gridline-color: transparent;
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                color: {C_TEXT};
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 0 12px;
                border-bottom: 1px solid {C_BORDER};
            }}
            QTableWidget::item:selected {{
                background-color: {C_NAV_ACTIVE};
                color: {C_TEXT};
            }}
            QHeaderView::section {{
                background-color: {C_CARD};
                color: {C_TEXT_MUTED};
                padding: 8px 12px;
                border: none;
                border-bottom: 1px solid {C_BORDER};
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QScrollBar:vertical {{
                background: {C_BG};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER};
                border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """

    def _progress_style(self, color: str) -> str:
        return f"""
            QProgressBar {{
                background-color: {C_BORDER};
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """

    def _bomb_progress_style(self, color: str) -> str:
        return f"""
            QProgressBar {{
                background-color: {C_BORDER};
                border-radius: 5px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 5px;
            }}
        """

    # ── 表格初始化 ─────────────────────────────────────────────────────────────

    def _setup_table(self) -> None:
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._populate_table()

    def _connect_signals(self) -> None:
        self._event_bus.mqtt_connected.connect(self._on_mqtt_connected)
        self._event_bus.node_status_changed.connect(self._on_status_changed)
        self._event_bus.node_came_online.connect(self._on_node_came_online)
        self._event_bus.node_went_offline.connect(self._on_node_went_offline)
        self._event_bus.node_activated.connect(self._on_node_activated)
        self._event_bus.node_reset.connect(self._on_node_reset)
        self._event_bus.game_started.connect(self._on_game_started)
        self._event_bus.team_eliminated.connect(self._on_team_eliminated)
        self._event_bus.team_victory.connect(self._on_team_victory)
        self._event_bus.bomb_activated.connect(self._on_bomb_activated)
        self._event_bus.bomb_tick.connect(self._on_bomb_tick)
        self._event_bus.bomb_defused.connect(self._on_bomb_defused)
        if self._frpc_manager:
            self._frpc_manager.status_changed.connect(self._on_frpc_status_changed)
            self._frpc_manager.log_received.connect(self._on_frpc_log_received)
            self._frpc_manager.error_occurred.connect(self._on_frpc_log_received)

    def _populate_table(self) -> None:
        nodes = self._node_manager.get_all_nodes()
        self._table.setRowCount(len(nodes))
        self._node_to_row.clear()

        for row, (node_id, state) in enumerate(nodes.items()):
            self._update_row_at(row, node_id, state)
            self._node_to_row[node_id] = row
        self._update_stats()

    def _find_row(self, node_id: str) -> int:
        return self._node_to_row.get(node_id, -1)

    def _update_row_at(self, row: int, node_id: str, state: "NodeState") -> None:
        is_online = state.status == OnlineStatus.ONLINE
        row_data = [
            node_id,
            state.node_type.value,
            "在线" if is_online else "离线",
            f"队伍 {state.active_team}" if state.active_team else "—",
            state.last_heartbeat.strftime("%H:%M:%S") if state.last_heartbeat else "—",
        ]
        for col, text in enumerate(row_data):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == self.COL_STATUS:
                item.setForeground(QColor(C_SUCCESS if is_online else C_DANGER))
            elif col == self.COL_TEAM and state.active_team:
                item.setForeground(QColor(TEAM_COLORS.get(state.active_team, C_TEXT)))
            else:
                item.setForeground(QColor(C_TEXT))
            self._table.setItem(row, col, item)
        self._table.setRowHeight(row, 44)

    def _update_row(self, node_id: str, state: "NodeState") -> None:
        row = self._find_row(node_id)
        if row == -1:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._node_to_row[node_id] = row
        self._update_row_at(row, node_id, state)
        self._update_stats()

    # ── 切页 ───────────────────────────────────────────────────────────────────

    def _switch_page(self, index: int) -> None:
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        self._stack.setCurrentIndex(index)
        self._page_title.setText(self._page_titles[index])

    # ── Node Slots ─────────────────────────────────────────────────────────────

    @Slot(str, object)
    def _on_status_changed(self, node_id: str, state: "NodeState") -> None:
        self._update_row(node_id, state)

    @Slot(str, object)
    def _on_node_came_online(self, node_id: str, state: "NodeState") -> None:
        self._update_row(node_id, state)
        self._status_label.setText(f"节点 {node_id} 上线")
        self._conn_dot.set_color(C_SUCCESS)
        self._conn_label.setText("节点在线")

    @Slot()
    def _on_mqtt_connected(self) -> None:
        self._audio_player.play_sys_online()
        self._conn_dot.set_color(C_SUCCESS)
        self._conn_label.setText("已连接")

    @Slot(str, object)
    def _on_node_went_offline(self, node_id: str, state: "NodeState") -> None:
        self._update_row(node_id, state)
        self._status_label.setText(f"节点 {node_id} 离线")
        if self._game_manager:
            self._game_manager.on_node_went_offline(node_id, state)

    @Slot(str, int, object)
    def _on_node_activated(self, node_id: str, team: str, state: "NodeState") -> None:
        self._update_row(node_id, state)
        self._status_label.setText(f"节点 {node_id} 激活 → 队伍 {team}")
        if self._game_manager:
            from game_manager import GameState

            if node_id.startswith("STA"):
                was_idle = self._game_manager.game_state == GameState.IDLE
                if was_idle:
                    self._audio_player.play_activated(team)
                self._game_manager.on_sta_activated(
                    node_id, team, self._node_manager.get_all_nodes()
                )
                if was_idle:
                    self._update_team_card(team, "已激活")
            elif node_id.startswith("DET"):
                self._audio_player.play_activated(team)
                self._game_manager.on_det_activated(
                    node_id, team, self._node_manager.get_all_nodes()
                )
                self._update_occupy_bars()
        else:
            self._audio_player.play_activated(team)

    @Slot(str, object)
    def _on_node_reset(self, node_id: str, state: "NodeState") -> None:
        self._update_row(node_id, state)
        self._status_label.setText(f"节点 {node_id} 已重置")

    @Slot()
    def _on_reset_btn_clicked(self) -> None:
        selected = self._table.selectedIndexes()
        if not selected:
            return
        node_id_item = self._table.item(selected[0].row(), self.COL_NODE_ID)
        if not node_id_item:
            return
        node_id = node_id_item.text()
        state = self._node_manager.reset_node(node_id)
        self._event_bus.node_reset.emit(node_id, state)

    # ── Game Slots ─────────────────────────────────────────────────────────────

    @Slot()
    def _on_game_started(self) -> None:
        self._audio_player.play_game_started()
        self._game_state_dot.set_color(C_SUCCESS)
        self._game_state_label.setText("RUNNING  ·  游戏进行中")
        self._game_state_label.setStyleSheet(
            f"color: {C_SUCCESS}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        self._status_label.setText("游戏已开始")
        self._start_game_btn.setEnabled(False)

    @Slot(str)
    def _on_team_eliminated(self, team: str) -> None:
        self._audio_player.play_team_eliminated(team)
        self._status_label.setText(f"队伍 {team} 已淘汰")
        self._update_team_card(team, "已淘汰", eliminated=True)

    @Slot(str)
    def _on_team_victory(self, team: str) -> None:
        self._audio_player.play_game_stopped()
        self._audio_player.play_team_victory(team)
        self._game_state_dot.set_color(C_WARNING)
        self._game_state_label.setText(f"ENDED  ·  队伍 {team} 获胜")
        self._game_state_label.setStyleSheet(
            f"color: {C_WARNING}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        self._status_label.setText(f"队伍 {team} 获胜！游戏结束")
        self._start_game_btn.setEnabled(True)
        self._bomb_status_card.setVisible(False)
        self._game_over_bar.setVisible(True)

    @Slot()
    def _on_bomb_activated(self) -> None:
        self._audio_player.play_bomb_activated()
        self._status_label.setText("炸弹已激活，40s 倒计时")
        self._bomb_status_card.setVisible(True)
        self._bomb_timer_label.setText("40")
        self._bomb_progress.setValue(40)

    @Slot(int)
    def _on_bomb_tick(self, remaining: int) -> None:
        self._bomb_timer_label.setText(str(remaining))
        self._bomb_progress.setValue(remaining)
        color = (
            C_DANGER
            if remaining <= 10
            else (C_WARNING if remaining <= 20 else C_WARNING)
        )
        self._bomb_timer_label.setStyleSheet(
            f"color: {color}; font-size: 56px; font-weight: bold; background: transparent;"
        )
        self._bomb_progress.setStyleSheet(self._bomb_progress_style(color))

    @Slot()
    def _on_bomb_defused(self) -> None:
        self._audio_player.play_bomb_defused()
        self._status_label.setText("炸弹已拆除，CT 队胜利")
        self._bomb_status_card.setVisible(False)

    @Slot()
    def _on_start_game_clicked(self) -> None:
        from game_manager import BombConfig, GameManager, GameMode

        mode_map = {
            "征服": GameMode.CONQUEST,
            "占领": GameMode.OCCUPY,
            "爆破": GameMode.BOMB,
        }
        mode = mode_map.get(self._current_mode, GameMode.CONQUEST)
        team_count = self._current_team_count
        participating_teams = [chr(ord("A") + i) for i in range(team_count)]
        self._current_participating_teams = participating_teams

        bomb_config = None
        if mode == GameMode.BOMB:
            bomb_config = BombConfig(
                self._bomb_attacker_combo.currentText(),
                self._bomb_defender_combo.currentText(),
                self._bomb_node_input.currentText(),
            )

        self._game_manager = GameManager(
            mode, team_count, participating_teams, self._event_bus, bomb_config
        )

        for team in ["A", "B", "C", "D"]:
            if team in participating_teams:
                self._update_team_card(team, "等待激活")
            else:
                self._update_team_card(team, "未参与")

        self._occupy_card.setVisible(mode == GameMode.OCCUPY)
        self._bomb_status_card.setVisible(False)
        self._game_over_bar.setVisible(False)
        self._game_state_dot.set_color(C_TEXT_MUTED)
        self._game_state_label.setText("IDLE  ·  等待节点激活")
        self._game_state_label.setStyleSheet(
            f"color: {C_TEXT_SEC}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        self._status_label.setText(f"等待 {team_count} 个 STA 节点激活...")
        logger.info(f"游戏已启动: 模式={mode.value}, 队伍数={team_count}")
        self._switch_page(2)

    @Slot()
    def _on_reset_game_clicked(self) -> None:
        if self._game_manager:
            self._game_manager.reset()
        self._start_game_btn.setEnabled(True)
        self._bomb_status_card.setVisible(False)
        self._occupy_card.setVisible(False)
        self._game_over_bar.setVisible(False)
        self._game_state_dot.set_color(C_TEXT_MUTED)
        self._game_state_label.setText("IDLE  ·  等待游戏开始")
        self._game_state_label.setStyleSheet(
            f"color: {C_TEXT_SEC}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        self._status_label.setText("游戏已重置")
        for team in ["A", "B", "C", "D"]:
            if team in self._current_participating_teams:
                self._update_team_card(team, "等待激活")
            else:
                self._update_team_card(team, "未参与")
