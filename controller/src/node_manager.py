import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, Signal

from .config import HEARTBEAT_TIMEOUT, WATCHDOG_INTERVAL
from .event_bus import EventBus

logger = logging.getLogger(__name__)


class NodeType(Enum):
    STA = "STA"
    DET = "DET"
    UNKNOWN = "UNKNOWN"


class OnlineStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"


@dataclass
class NodeState:
    node_id: str
    node_type: NodeType
    status: OnlineStatus = OnlineStatus.OFFLINE
    active_team: str = ""  # "" 未激活，"A"-"D" 表示队伍
    last_heartbeat: Optional[datetime] = None
    last_activated: Optional[datetime] = None


class NodeManager(QObject):
    """节点状态管理器"""

    node_status_changed = Signal(str, object)
    node_came_online = Signal(str, object)
    node_went_offline = Signal(str, object)
    node_activated = Signal(str, str, object)
    node_reset = Signal(str, object)

    def __init__(self, event_bus: "EventBus") -> None:
        super().__init__()
        self._nodes: dict[str, NodeState] = {}
        self._event_bus = event_bus

        self._connect_signals_to_bus()

    def _connect_signals_to_bus(self) -> None:
        """将 NodeManager 的信号转发到全局 EventBus"""
        self.node_status_changed.connect(self._event_bus.node_status_changed)
        self.node_came_online.connect(self._event_bus.node_came_online)
        self.node_went_offline.connect(self._event_bus.node_went_offline)
        self.node_activated.connect(self._event_bus.node_activated)
        self.node_reset.connect(self._event_bus.node_reset)

    def _infer_node_type(self, node_id: str) -> NodeType:
        if node_id.startswith("STA"):
            return NodeType.STA
        elif node_id.startswith("DET"):
            return NodeType.DET
        return NodeType.UNKNOWN

    def _get_or_create(self, node_id: str) -> NodeState:
        if node_id not in self._nodes:
            node_type = self._infer_node_type(node_id)
            state = NodeState(node_id=node_id, node_type=node_type)
            self._nodes[node_id] = state
            logger.info(f"发现新节点: {node_id} (类型: {node_type.value})")
        return self._nodes[node_id]

    def handle_heartbeat(self, node_id: str) -> tuple[bool, NodeState]:
        """处理心跳"""
        state = self._get_or_create(node_id)
        came_online = state.status != OnlineStatus.ONLINE

        state.status = OnlineStatus.ONLINE
        state.last_heartbeat = datetime.now()

        self.node_status_changed.emit(node_id, state)

        if came_online:
            self.node_came_online.emit(node_id, state)

        return came_online, state

    def handle_activation(self, node_id: str, team: int) -> NodeState:
        """处理激活"""
        state = self._get_or_create(node_id)
        team_char = chr(ord("A") + team - 1)

        state.active_team = team_char
        state.last_activated = datetime.now()

        logger.info(f"节点 {node_id} 激活为队伍 {team_char}")

        self.node_activated.emit(node_id, team_char, state)
        self.node_status_changed.emit(node_id, state)

        return state

    def mark_offline(self, node_id: str) -> NodeState:
        """标记为离线（看门狗调用）"""
        state = self._get_or_create(node_id)
        if state.status == OnlineStatus.OFFLINE:
            return state

        state.status = OnlineStatus.OFFLINE
        logger.warning(f"节点 {node_id} 心跳超时，标记为离线")

        self.node_went_offline.emit(node_id, state)
        self.node_status_changed.emit(node_id, state)

        return state

    def reset_node(self, node_id: str) -> NodeState:
        """手动重置节点"""
        state = self._get_or_create(node_id)
        if state.active_team == "":
            return state

        state.active_team = ""
        logger.info(f"节点 {node_id} 激活状态已重置")

        self.node_reset.emit(node_id, state)
        self.node_status_changed.emit(node_id, state)

        return state

    def get_node(self, node_id: str) -> Optional[NodeState]:
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> dict[str, NodeState]:
        return dict(self._nodes)

    async def heartbeat_watchdog(self) -> None:
        while True:
            await asyncio.sleep(WATCHDOG_INTERVAL)
            now = datetime.now()

            for state in list(self._nodes.values()):
                if (
                    state.status == OnlineStatus.ONLINE
                    and state.last_heartbeat
                    and (now - state.last_heartbeat).total_seconds() > HEARTBEAT_TIMEOUT
                ):
                    self.mark_offline(state.node_id)
