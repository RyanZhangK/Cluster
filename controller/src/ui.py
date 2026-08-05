import logging
from collections import deque
from typing import TYPE_CHECKING, Any, ClassVar

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .audio_player import AudioPlayer
from .event_bus import EventBus
from .node_manager import NodeManager, OnlineStatus
from .styles import (
    C_BG,
    C_BORDER,
    C_CARD,
    C_DANGER,
    C_SUCCESS,
    C_TEXT,
    C_TEXT_MUTED,
    C_TEXT_SEC,
    C_WARNING,
    TEAM_COLORS,
    progress_style,
    toggle_btn_style,
)
from .ui_debug_page import build_debug_page
from .ui_frpc_page import build_frpc_page, collect_frpc_config
from .ui_game_ctrl import build_game_ctrl_page
from .ui_game_status import build_game_status_page
from .ui_manual_page import build_manual_page
from .ui_node_page import build_node_page
from .ui_sidebar import build_sidebar
from .ui_topbar import build_topbar

if TYPE_CHECKING:
    from frpc_manager import FrpcManager
    from game_manager import GameManager
    from node_manager import NodeState

logger = logging.getLogger(__name__)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ─── 主窗口 ───────────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    COL_NODE_ID = 0
    COL_TYPE = 1
    COL_STATUS = 2
    COL_TEAM = 3
    COL_HEARTBEAT = 4
    COLUMN_HEADERS: ClassVar[list[str]] = [
        "节点ID",
        "类型",
        "在线状态",
        "激活队伍",
        "最后心跳",
    ]

    LEVEL_MAP: ClassVar[dict[str, int]] = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
    }
    LEVEL_COLORS: ClassVar[dict[int, str]] = {
        10: "#888888",
        20: "#CCCCCC",
        30: "#FFCC00",
        40: "#FF4444",
        50: "#FF4444",
    }

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
        self._frpc_manager: FrpcManager | None = frpc_manager
        self._game_manager: GameManager | None = None
        self._current_mode = "征服"
        self._current_team_count = 2
        self._current_participating_teams: list[str] = []

        self._filter_text = ""
        self._filter_type = "全部类型"
        self._filter_status = "全部状态"
        self._filter_team = "全部队伍"

        self._log_buffer: deque[tuple[int, str]] = deque(maxlen=500)
        self._mqtt_buffer: deque[str] = deque(maxlen=500)
        self._mqtt_pending: list[str] = []
        self._mqtt_paused = False

        self._bomb_attacker_combo = QComboBox()
        self._bomb_defender_combo = QComboBox()
        self._bomb_node_input = QComboBox()

        self._frpc_server_addr: QLabel = QLabel()
        self._frpc_auth_token: QLabel = QLabel()

        # ── Widget refs set by page builders (unknown to type checker) ───────
        self._nav_nodes: Any = None
        self._nav_game_ctrl: Any = None
        self._nav_game_status: Any = None
        self._nav_manual: Any = None
        self._nav_frpc: Any = None
        self._nav_debug: Any = None
        self._conn_dot: Any = None
        self._conn_label: Any = None
        self._page_title: Any = None
        self._status_label: Any = None
        self._stat_val_total: Any = None
        self._stat_val_online: Any = None
        self._stat_val_offline: Any = None
        self._venue_lock_btn: Any = None
        self._search_input: Any = None
        self._filter_type_combo: Any = None
        self._filter_status_combo: Any = None
        self._filter_team_combo: Any = None
        self._table: Any = None
        self._mode_btns: Any = None
        self._team_count_btns: Any = None
        self._bomb_card: Any = None
        self._start_game_btn: Any = None
        self._game_state_dot: Any = None
        self._game_state_label: Any = None
        self._team_cards: Any = None
        self._occupy_card: Any = None
        self._occupy_bars: Any = None
        self._bomb_status_card: Any = None
        self._bomb_timer_label: Any = None
        self._bomb_progress: Any = None
        self._game_over_bar: Any = None
        self._frpc_status_dot: Any = None
        self._frpc_status_label: Any = None
        self._frpc_start_btn: Any = None
        self._frpc_stop_btn: Any = None
        self._frpc_log: Any = None
        self._proxy_table: Any = None
        self._proxy_name_input: Any = None
        self._proxy_type_combo: Any = None
        self._proxy_local_ip: Any = None
        self._proxy_local_port: Any = None
        self._proxy_remote_port: Any = None
        self._log_level_combo: Any = None
        self._log_view: Any = None
        self._mqtt_pause_btn: Any = None
        self._mqtt_count_label: Any = None
        self._mqtt_view: Any = None

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

        root_layout.addWidget(build_sidebar(self))

        content = QFrame()
        content.setStyleSheet(f"background-color: {C_BG};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(build_topbar(self))

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {C_BG};")
        self._stack.addWidget(build_node_page(self))
        self._stack.addWidget(build_game_ctrl_page(self))
        self._stack.addWidget(build_game_status_page(self))
        self._stack.addWidget(build_manual_page(self))
        self._stack.addWidget(build_frpc_page(self))
        self._stack.addWidget(build_debug_page(self))
        content_layout.addWidget(self._stack)

        root_layout.addWidget(content, 1)

        self._nav_buttons = [
            self._nav_nodes,
            self._nav_game_ctrl,
            self._nav_game_status,
            self._nav_manual,
            self._nav_frpc,
            self._nav_debug,
        ]
        self._page_titles = [
            "节点监控",
            "游戏控制",
            "游戏状态",
            "紧急手动",
            "Frpc管理",
            "调试",
        ]

    # ── 统计 & 场馆锁定 ────────────────────────────────────────────────────────

    def _update_stats(self) -> None:
        nodes = self._node_manager.get_all_nodes()
        total = len(nodes)
        online = sum(1 for s in nodes.values() if s.status == OnlineStatus.ONLINE)
        self._stat_val_total.setText(str(total))
        self._stat_val_online.setText(str(online))
        self._stat_val_offline.setText(str(total - online))

    def _on_venue_lock_toggled(self, checked: bool) -> None:
        """场馆锁定切换：LOCK:1 锁定（LED 灭），LOCK:0 解锁（LED 亮）。"""
        self._venue_lock_btn.setText("锁定" if checked else "解锁")
        self._venue_lock_btn.setStyleSheet(toggle_btn_style(checked))

        self._event_bus.venue_lock_changed.emit(checked)
        logger.info(f"场馆锁定状态变更: {'锁定' if checked else '解锁'}")

    # ── 游戏控制交互 ───────────────────────────────────────────────────────────

    def _on_mode_btn_clicked(self, mode: str) -> None:
        self._current_mode = mode
        for m, btn in self._mode_btns.items():
            btn.setChecked(m == mode)
            btn.setStyleSheet(toggle_btn_style(m == mode))
        self._bomb_card.setVisible(mode == "爆破")

    def _on_team_count_clicked(self, count: int) -> None:
        self._current_team_count = count
        for n, btn in self._team_count_btns.items():
            btn.setChecked(n == count)
            btn.setStyleSheet(toggle_btn_style(n == count))

    # ── 手动音效 ───────────────────────────────────────────────────────────────

    def _on_manual_play(self, key: str) -> None:
        self._audio_player.play_immediate(key)

    # ── 游戏状态 UI ────────────────────────────────────────────────────────────

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
        self._event_bus.log_received.connect(self._on_log_received)
        self._event_bus.mqtt_message_received.connect(self._on_mqtt_message)

        if self._frpc_manager:
            self._frpc_manager.status_changed.connect(self._on_frpc_status_changed)
            self._frpc_manager.log_received.connect(self._on_frpc_log_received)
            self._frpc_manager.error_occurred.connect(self._on_frpc_log_received)

    def _populate_table(self) -> None:
        nodes = self._node_manager.get_all_nodes()
        filtered = self._apply_filters(nodes)
        self._table.setRowCount(len(filtered))

        for row, (node_id, state) in enumerate(filtered.items()):
            self._update_row_at(row, node_id, state)
        self._update_stats()

    def _apply_filters(self, nodes: dict[str, "NodeState"]) -> dict[str, "NodeState"]:
        filtered = {}
        for node_id, state in nodes.items():
            if self._filter_text and self._filter_text not in node_id.lower():
                continue
            if (
                self._filter_type != "全部类型"
                and state.node_type.value != self._filter_type
            ):
                continue
            if self._filter_status == "在线" and state.status != OnlineStatus.ONLINE:
                continue
            if self._filter_status == "离线" and state.status != OnlineStatus.OFFLINE:
                continue
            if self._filter_team == "未激活" and state.active_team:
                continue
            if (
                self._filter_team not in ("全部队伍", "未激活")
                and state.active_team != self._filter_team
            ):
                continue
            filtered[node_id] = state
        return filtered

    def _find_row(self, node_id: str) -> int:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, self.COL_NODE_ID)
            if item and item.text() == node_id:
                return row
        return -1

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
        self._update_row_at(row, node_id, state)
        self._update_stats()

    # ── 切页 ───────────────────────────────────────────────────────────────────

    def _switch_page(self, index: int) -> None:
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        self._stack.setCurrentIndex(index)
        import controller.src.main as m

        m._stack_index = index
        self._page_title.setText(self._page_titles[index])

    # ── Node Slots ─────────────────────────────────────────────────────────────

    @Slot(str, object)
    def _on_status_changed(self, _node_id: str, _state: "NodeState") -> None:
        self._populate_table()

    @Slot(str, object)
    def _on_node_came_online(self, node_id: str, _state: "NodeState") -> None:
        self._populate_table()
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
        self._populate_table()
        self._status_label.setText(f"节点 {node_id} 离线")
        if self._game_manager:
            self._game_manager.on_node_went_offline(node_id, state)

    @Slot(str, str, object)
    def _on_node_activated(self, node_id: str, team: str, _state: "NodeState") -> None:
        self._populate_table()
        self._status_label.setText(f"节点 {node_id} 激活 → 队伍 {team}")
        if self._game_manager:
            from .game_manager import GameMode, GameState

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
                # DET 节点按游戏模式触发不同音频
                if self._game_manager.mode == GameMode.OCCUPY:
                    self._audio_player.play_hotpoint(team)
                # Bomb 模式音频由 bomb_activated/bomb_defused 事件触发，此处不播
                self._game_manager.on_det_activated(
                    node_id, team, self._node_manager.get_all_nodes()
                )
                self._update_occupy_bars()
        elif node_id.startswith("STA"):
            self._audio_player.play_activated(team)

    @Slot(str, object)
    def _on_node_reset(self, node_id: str, _state: "NodeState") -> None:
        self._populate_table()
        self._status_label.setText(f"节点 {node_id} 已重置")

    @Slot()
    def _on_filter_changed(self) -> None:
        self._filter_text = self._search_input.text().strip().lower()
        self._filter_type = self._filter_type_combo.currentText()
        self._filter_status = self._filter_status_combo.currentText()
        self._filter_team = self._filter_team_combo.currentText()
        self._populate_table()

    @Slot()
    def _on_select_all(self) -> None:
        self._table.selectAll()

    @Slot()
    def _on_invert_select(self) -> None:
        from PySide6.QtCore import QItemSelectionModel

        sm = self._table.selectionModel()
        fl = QItemSelectionModel.SelectionFlag
        for row in range(self._table.rowCount()):
            idx = self._table.model().index(row, 0)
            sm.select(idx, fl.Toggle | fl.Rows)

    @Slot()
    def _on_reset_all_clicked(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.warning(
            self,
            "确认重置",
            "确定要重置所有节点的激活状态吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for node_id in list(self._node_manager.get_all_nodes().keys()):
            state = self._node_manager.reset_node(node_id)
            self._event_bus.node_reset.emit(node_id, state)

    @Slot()
    def _on_reset_btn_clicked(self) -> None:
        selected_rows: set[int] = set()
        for index in self._table.selectedIndexes():
            selected_rows.add(index.row())
        if not selected_rows:
            return
        for row in selected_rows:
            node_id_item = self._table.item(row, self.COL_NODE_ID)
            if not node_id_item:
                continue
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
        color = C_DANGER if remaining <= 10 else C_WARNING
        self._bomb_timer_label.setStyleSheet(
            f"color: {color}; font-size: 56px; font-weight: bold; background: transparent;"
        )
        self._bomb_progress.setStyleSheet(progress_style(color, 5))

    @Slot()
    def _on_bomb_defused(self) -> None:
        self._audio_player.play_bomb_defused()
        self._status_label.setText("炸弹已拆除，CT 队胜利")
        self._bomb_status_card.setVisible(False)

    @Slot()
    def _on_start_game_clicked(self) -> None:
        from .game_manager import BombConfig, GameManager, GameMode

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

    # ── Debug Slots ───────────────────────────────────────────────────────────

    @Slot(str, int)
    def _on_log_received(self, message: str, levelno: int) -> None:
        self._log_buffer.append((levelno, message))
        min_level = self.LEVEL_MAP.get(self._log_level_combo.currentText(), 20)
        if levelno >= min_level:
            color = self.LEVEL_COLORS.get(levelno, "#CCCCCC")
            escaped = _escape_html(message)
            self._log_view.append(f'<span style="color: {color}">{escaped}</span>')
            scrollbar = self._log_view.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def _on_log_level_changed(self) -> None:
        min_level = self.LEVEL_MAP.get(self._log_level_combo.currentText(), 20)
        self._log_view.clear()
        for levelno, msg in self._log_buffer:
            if levelno >= min_level:
                color = self.LEVEL_COLORS.get(levelno, "#CCCCCC")
                escaped = _escape_html(msg)
                self._log_view.append(f'<span style="color: {color}">{escaped}</span>')
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def _on_clear_log(self) -> None:
        self._log_buffer.clear()
        self._log_view.clear()

    @Slot(str, str, str)
    def _on_mqtt_message(self, topic: str, payload: str, timestamp: str) -> None:
        html = (
            f'<span style="color: #66ccff">{timestamp}</span>'
            f'  <span style="color: #888888">{topic}</span>'
            f'  ←  <span style="color: {C_TEXT}">{payload}</span>'
        )
        self._mqtt_buffer.append(f"{timestamp}  {topic}  ←  {payload}")
        self._mqtt_pending.append(html)

    @Slot()
    def _flush_mqtt(self) -> None:
        if self._mqtt_paused or not self._mqtt_pending:
            return
        cursor = self._mqtt_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for html in self._mqtt_pending:
            cursor.insertHtml(html + "<br>")
        self._mqtt_pending.clear()
        self._mqtt_count_label.setText(f"{len(self._mqtt_buffer)} 条")
        scrollbar = self._mqtt_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot(bool)
    def _on_mqtt_pause_toggle(self, checked: bool) -> None:
        self._mqtt_paused = checked
        if checked:
            self._mqtt_pause_btn.setText("继续")
            self._mqtt_pause_btn.setStyleSheet(toggle_btn_style(True))
        else:
            self._mqtt_pause_btn.setText("暂停")
            self._mqtt_pause_btn.setStyleSheet(toggle_btn_style(False))
            self._flush_mqtt()

    @Slot()
    def _on_clear_mqtt(self) -> None:
        self._mqtt_buffer.clear()
        self._mqtt_view.clear()
        self._mqtt_count_label.setText("0 条")

    # ── Frpc Slots ────────────────────────────────────────────────────────────

    @Slot()
    def _on_frpc_start(self) -> None:
        if self._frpc_manager is None:
            return
        config = collect_frpc_config(self)
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

    # ── 关机 ──────────────────────────────────────────────────────────────────

    @Slot()
    def _on_shutdown_clicked(self) -> None:
        if self._frpc_manager and self._frpc_manager.is_running:
            self._frpc_manager.stop()

        if self._game_manager:
            self._game_manager.reset()
            self._switch_page(0)

        self._audio_player.play_immediate("sys_offline")

        from PySide6.QtCore import QTimer

        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(200)
        self._shutdown_timer.timeout.connect(self._check_shutdown)
        self._shutdown_timer.start()

    def _check_shutdown(self) -> None:
        if self._audio_player.is_idle:
            self._shutdown_timer.stop()
            from PySide6.QtWidgets import QApplication

            QApplication.quit()
