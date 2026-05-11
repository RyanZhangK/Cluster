import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from .event_bus import EventBus
from .config import HEARTBEAT_TIMEOUT, WATCHDOG_INTERVAL

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


class NodeManager:
    def __init__(self, event_bus: "EventBus") -> None:
        self._nodes: dict[str, NodeState] = {}
        self._event_bus = event_bus

    def _infer_node_type(self, node_id: str) -> NodeType:
        """从 node_id 前缀推断节点类型。"""
        if node_id.startswith("STA"):
            return NodeType.STA
        elif node_id.startswith("DET"):
            return NodeType.DET
        else:
            return NodeType.UNKNOWN

    def _get_or_create(self, node_id: str) -> NodeState:
        """获取或创建节点状态。首次发现时自动创建。"""
        if node_id not in self._nodes:
            node_type = self._infer_node_type(node_id)
            state = NodeState(node_id=node_id, node_type=node_type)
            self._nodes[node_id] = state
            logger.info(f"发现新节点: {node_id} (类型: {node_type.value})")
        return self._nodes[node_id]

    def handle_heartbeat(self, node_id: str) -> tuple[bool, NodeState]:
        """
        处理心跳消息。
        返回 (came_online: bool, updated_state: NodeState)
        came_online=True 表示节点从离线状态恢复上线。
        """
        state = self._get_or_create(node_id)
        came_online = state.status != OnlineStatus.ONLINE
        state.status = OnlineStatus.ONLINE
        state.last_heartbeat = datetime.now()
        return came_online, state

    def handle_activation(self, node_id: str, team: int) -> NodeState:
        """处理激活消息，将队伍编号 1-4 转换为 A-D 后存储。"""
        state = self._get_or_create(node_id)
        team_char = chr(ord("A") + team - 1)  # 1->A, 2->B, 3->C, 4->D
        state.active_team = team_char
        state.last_activated = datetime.now()
        logger.info(f"节点 {node_id} 激活为队伍 {team_char}")
        return state

    def mark_offline(self, node_id: str) -> NodeState:
        """将节点标记为离线（由看门狗调用）。"""
        state = self._get_or_create(node_id)
        state.status = OnlineStatus.OFFLINE
        logger.warning(f"节点 {node_id} 心跳超时，标记为离线")
        return state

    def reset_node(self, node_id: str) -> NodeState:
        """手动重置节点激活状态。"""
        state = self._get_or_create(node_id)
        state.active_team = ""
        logger.info(f"节点 {node_id} 激活状态已重置")
        return state

    def get_node(self, node_id: str) -> Optional[NodeState]:
        """获取单个节点状态。"""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> dict[str, NodeState]:
        """返回所有节点状态的浅拷贝。"""
        return dict(self._nodes)

    async def heartbeat_watchdog(self) -> None:
        """
        后台协程：每 WATCHDOG_INTERVAL 秒检查一次所有节点心跳。
        超时则标记离线并 emit 信号。
        """
        while True:
            await asyncio.sleep(WATCHDOG_INTERVAL)
            now = datetime.now()
            for state in list(self._nodes.values()):
                if (
                    state.status == OnlineStatus.ONLINE
                    and state.last_heartbeat
                    and (now - state.last_heartbeat).total_seconds() > HEARTBEAT_TIMEOUT
                ):
                    updated = self.mark_offline(state.node_id)
                    self._event_bus.node_went_offline.emit(state.node_id, updated)
