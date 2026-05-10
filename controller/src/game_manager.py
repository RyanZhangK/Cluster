import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from event_bus import EventBus
    from node_manager import NodeState

logger = logging.getLogger(__name__)


class GameMode(Enum):
    CONQUEST = "conquest"
    OCCUPY = "occupy"
    BOMB = "bomb"


class GameState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ENDED = "ended"


@dataclass
class BombConfig:
    attacker_team: str
    defender_team: str
    bomb_node_id: str


class GameManager(QObject):
    """游戏状态管理器，处理三个游戏模式的业务逻辑。"""

    def __init__(
        self,
        mode: GameMode,
        team_count: int,
        participating_teams: list[str],
        event_bus: "EventBus",
        bomb_config: BombConfig | None = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.team_count = team_count
        self.participating_teams = set(participating_teams)
        self._event_bus = event_bus
        self.bomb_config = bomb_config

        self._game_state = GameState.IDLE
        self._sta_team_mapping: dict[str, str] = {}  # node_id → team（开始时记录）
        self._eliminated_teams: set[str] = set()
        self._det_activation: dict[str, str] = {}  # node_id → team（占领模式）
        self._bomb_task: asyncio.Task | None = None
        self._bomb_remaining: int = 0

        logger.info(
            f"GameManager 初始化: 模式={mode.value}, 队伍数={team_count}, 队伍={participating_teams}"
        )

    def on_sta_activated(self, node_id: str, team: str, nodes: dict) -> None:
        """STA 节点激活时调用。"""
        if self._game_state == GameState.IDLE:
            # 开始阶段：记录节点↔队伍映射
            self._sta_team_mapping[node_id] = team
            logger.info(f"记录 STA 节点: {node_id} → 队伍 {team}")

            # 检查开始条件
            if len(self._sta_team_mapping) == self.team_count:
                self._start_game()

        elif self._game_state == GameState.RUNNING:
            if self.mode == GameMode.CONQUEST:
                # 征服模式：STA 节点再次激活 → 对应队伍淘汰
                if node_id in self._sta_team_mapping:
                    eliminated_team = self._sta_team_mapping[node_id]
                    if eliminated_team not in self._eliminated_teams:
                        self._eliminate_team(eliminated_team)
                        self._check_conquest_victory()

            elif self.mode == GameMode.BOMB:
                # 爆破模式：STA 激活可能触发炸弹激活或拆除
                pass

    def on_det_activated(self, node_id: str, team: str, nodes: dict) -> None:
        """DET 节点激活时调用。"""
        if self._game_state != GameState.RUNNING:
            return

        if self.mode == GameMode.OCCUPY:
            # 占领模式：统计队伍激活的 DET 节点数
            self._det_activation[node_id] = team
            self._check_occupy_victory(nodes)

        elif self.mode == GameMode.BOMB:
            # 爆破模式：检查是否是炸弹节点
            if node_id == self.bomb_config.bomb_node_id:
                if team == self.bomb_config.attacker_team:
                    # 装弹方激活炸弹
                    self._activate_bomb()
                elif team == self.bomb_config.defender_team:
                    # 拆弹方拆除炸弹
                    self._defuse_bomb()

    def on_node_went_offline(self, node_id: str, state: "NodeState") -> None:
        """节点离线时调用。"""
        if self._game_state != GameState.RUNNING:
            return

        # 爆破模式：如果炸弹节点离线，取消倒计时
        if self.mode == GameMode.BOMB and node_id == self.bomb_config.bomb_node_id:
            if self._bomb_task and not self._bomb_task.done():
                self._bomb_task.cancel()
                self._bomb_task = None
                logger.warning("炸弹节点离线，倒计时已取消")

    def _start_game(self) -> None:
        """游戏开始。"""
        self._game_state = GameState.RUNNING
        logger.info(f"游戏开始！节点映射: {self._sta_team_mapping}")
        self._event_bus.game_started.emit()

    def _eliminate_team(self, team: str) -> None:
        """淘汰队伍。"""
        self._eliminated_teams.add(team)
        logger.info(f"队伍 {team} 已淘汰")
        self._event_bus.team_eliminated.emit(team)

    def _check_conquest_victory(self) -> None:
        """检查征服模式胜利条件。"""
        remaining = len(self.participating_teams) - len(self._eliminated_teams)
        if remaining == 1:
            winner = (self.participating_teams - self._eliminated_teams).pop()
            self._end_game(winner)

    def _check_occupy_victory(self, nodes: dict) -> None:
        """检查占领模式胜利条件。"""
        # 统计在线 DET 节点总数
        online_det_count = sum(
            1
            for node_id, state in nodes.items()
            if node_id.startswith("DET") and state.status.value == "online"
        )

        if online_det_count == 0:
            logger.warning("没有在线 DET 节点，无法判断占领胜利")
            return

        # 统计各队伍激活的 DET 节点数
        team_det_count = {}
        for node_id, team in self._det_activation.items():
            team_det_count[team] = team_det_count.get(team, 0) + 1

        # 检查是否有队伍超过半数
        threshold = online_det_count / 2
        for team, count in team_det_count.items():
            if count > threshold:
                logger.info(
                    f"队伍 {team} 占领 {count}/{online_det_count} DET 节点，超过半数"
                )
                self._end_game(team)
                return

    def _activate_bomb(self) -> None:
        """爆破模式：炸弹激活。"""
        logger.info("炸弹已激活，开始 40s 倒计时")
        self._event_bus.bomb_activated.emit()
        self._bomb_remaining = 40
        self._bomb_task = asyncio.create_task(self._bomb_countdown())

    async def _bomb_countdown(self) -> None:
        """爆破模式：40s 倒计时。"""
        try:
            while self._bomb_remaining > 0:
                await asyncio.sleep(1)
                self._bomb_remaining -= 1
                self._event_bus.bomb_tick.emit(self._bomb_remaining)
                logger.debug(f"炸弹倒计时: {self._bomb_remaining}s")

            # 倒计时结束，T 队胜利
            logger.info("炸弹倒计时结束，T 队胜利")
            self._event_bus.bomb_exploded.emit()
            self._end_game(self.bomb_config.attacker_team)
        except asyncio.CancelledError:
            logger.info("炸弹倒计时已取消")

    def _defuse_bomb(self) -> None:
        """爆破模式：炸弹拆除。"""
        if self._bomb_task and not self._bomb_task.done():
            self._bomb_task.cancel()
            self._bomb_task = None
        logger.info("炸弹已拆除，CT 队胜利")
        self._event_bus.bomb_defused.emit()
        self._end_game(self.bomb_config.defender_team)

    def _end_game(self, winner: str) -> None:
        """游戏结束。"""
        self._game_state = GameState.ENDED
        logger.info(f"游戏结束！队伍 {winner} 获胜")
        self._event_bus.team_victory.emit(winner)

    @property
    def game_state(self) -> GameState:
        return self._game_state

    def reset(self) -> None:
        """重置游戏状态。"""
        if self._bomb_task and not self._bomb_task.done():
            self._bomb_task.cancel()
        self._game_state = GameState.IDLE
        self._sta_team_mapping.clear()
        self._eliminated_teams.clear()
        self._det_activation.clear()
        self._bomb_task = None
        self._bomb_remaining = 0
        logger.info("游戏已重置")
