from unittest.mock import MagicMock

import pytest

from controller.src.game_manager import BombConfig, GameManager, GameMode, GameState
from controller.src.node_manager import NodeState, NodeType, OnlineStatus


@pytest.fixture
def conquest_manager() -> GameManager:
    event_bus = MagicMock()
    gm = GameManager(
        mode=GameMode.CONQUEST,
        team_count=2,
        participating_teams=["A", "B"],
        event_bus=event_bus,
    )
    return gm


@pytest.fixture
def occupy_manager() -> GameManager:
    event_bus = MagicMock()
    gm = GameManager(
        mode=GameMode.OCCUPY,
        team_count=2,
        participating_teams=["A", "B"],
        event_bus=event_bus,
    )
    return gm


@pytest.fixture
def bomb_manager() -> GameManager:
    event_bus = MagicMock()
    gm = GameManager(
        mode=GameMode.BOMB,
        team_count=2,
        participating_teams=["T", "CT"],
        event_bus=event_bus,
        bomb_config=BombConfig(
            attacker_team="T",
            defender_team="CT",
            bomb_node_id="DET01",
        ),
    )
    return gm


def make_det_states(count: int, online: int | None = None) -> dict[str, NodeState]:
    online = online if online is not None else count
    nodes: dict[str, NodeState] = {}
    for i in range(count):
        state = NodeState(
            node_id=f"DET{i + 1:02d}",
            node_type=NodeType.DET,
            status=OnlineStatus.ONLINE if i < online else OnlineStatus.OFFLINE,
        )
        nodes[f"DET{i + 1:02d}"] = state
    return nodes


class TestGameManagerInitialState:
    def test_initial_state_is_idle(self, conquest_manager: GameManager) -> None:
        assert conquest_manager.game_state == GameState.IDLE

    def test_conquest_starts_when_all_teams_activated(
        self, conquest_manager: GameManager
    ) -> None:
        conquest_manager.on_sta_activated("STA01", "A", None)
        assert conquest_manager.game_state == GameState.IDLE
        conquest_manager.on_sta_activated("STA02", "B", None)
        assert conquest_manager.game_state == GameState.RUNNING

    def test_conquest_does_not_start_with_duplicate_team(
        self, conquest_manager: GameManager
    ) -> None:
        conquest_manager.on_sta_activated("STA01", "A", None)
        conquest_manager.on_sta_activated("STA02", "A", None)
        assert conquest_manager.game_state == GameState.IDLE

    def test_conquest_requires_correct_team_count(
        self, conquest_manager: GameManager
    ) -> None:
        conquest_manager.on_sta_activated("STA01", "A", None)
        conquest_manager.on_sta_activated("STA02", "B", None)
        conquest_manager.reset()
        conquest_manager.on_sta_activated("STA03", "C", None)
        assert conquest_manager.game_state == GameState.IDLE


class TestConquestMode:
    def test_eliminate_team_on_sta_reactivation(
        self, conquest_manager: GameManager
    ) -> None:
        conquest_manager.on_sta_activated("STA01", "A", None)
        conquest_manager.on_sta_activated("STA02", "B", None)
        conquest_manager.on_sta_activated("STA01", "A", None)
        assert "A" in conquest_manager._eliminated_teams

    def test_conquest_victory_on_last_team_eliminated(
        self, conquest_manager: GameManager
    ) -> None:
        conquest_manager.on_sta_activated("STA01", "A", None)
        conquest_manager.on_sta_activated("STA02", "B", None)
        conquest_manager.on_sta_activated("STA01", "A", None)
        assert conquest_manager.game_state == GameState.ENDED

    def test_reactivation_in_idle_does_not_eliminate(
        self, conquest_manager: GameManager
    ) -> None:
        conquest_manager.on_sta_activated("STA01", "A", None)
        conquest_manager.on_sta_activated("STA02", "B", None)
        conquest_manager.reset()
        conquest_manager.on_sta_activated("STA01", "A", None)
        assert len(conquest_manager._eliminated_teams) == 0


class TestOccupyMode:
    def test_occupy_majority_wins(self, occupy_manager: GameManager) -> None:
        occupy_manager._game_state = GameState.RUNNING
        nodes = make_det_states(3)
        occupy_manager.on_det_activated("DET01", "A", nodes)
        occupy_manager.on_det_activated("DET02", "A", nodes)
        assert occupy_manager.game_state == GameState.ENDED

    def test_occupy_minority_does_not_win(self, occupy_manager: GameManager) -> None:
        occupy_manager._game_state = GameState.RUNNING
        nodes = make_det_states(3)
        occupy_manager.on_det_activated("DET01", "A", nodes)
        assert occupy_manager.game_state != GameState.ENDED

    def test_occupy_does_nothing_when_idle(self, occupy_manager: GameManager) -> None:
        nodes = make_det_states(3)
        occupy_manager.on_det_activated("DET01", "A", nodes)
        assert len(occupy_manager._det_activation) == 0

    def test_occupy_tie_does_not_win(self, occupy_manager: GameManager) -> None:
        occupy_manager._game_state = GameState.RUNNING
        nodes = make_det_states(4)
        occupy_manager.on_det_activated("DET01", "A", nodes)
        occupy_manager.on_det_activated("DET02", "A", nodes)
        occupy_manager.on_det_activated("DET03", "B", nodes)
        occupy_manager.on_det_activated("DET04", "B", nodes)
        assert occupy_manager.game_state != GameState.ENDED

    def test_occupy_three_vs_one_wins(self, occupy_manager: GameManager) -> None:
        occupy_manager._game_state = GameState.RUNNING
        nodes = make_det_states(4)
        occupy_manager.on_det_activated("DET01", "A", nodes)
        occupy_manager.on_det_activated("DET02", "A", nodes)
        occupy_manager.on_det_activated("DET03", "A", nodes)
        assert occupy_manager.game_state == GameState.ENDED


class TestBombMode:
    def test_bomb_activate_starts_timer(self, bomb_manager: GameManager) -> None:
        bomb_manager._game_state = GameState.RUNNING
        bomb_manager.on_det_activated("DET01", "T", {})
        assert bomb_manager._bomb_remaining == 40
        assert bomb_manager._bomb_timer is not None

    def test_bomb_defuse_ends_game(self, bomb_manager: GameManager) -> None:
        bomb_manager._game_state = GameState.RUNNING
        bomb_manager._activate_bomb()
        bomb_manager.on_det_activated("DET01", "CT", {})
        assert bomb_manager.game_state == GameState.ENDED
        assert bomb_manager._bomb_timer is None

    def test_bomb_node_offline_cancels(self, bomb_manager: GameManager) -> None:
        bomb_manager._game_state = GameState.RUNNING
        bomb_manager._activate_bomb()
        state = NodeState(node_id="DET01", node_type=NodeType.DET)
        bomb_manager.on_node_went_offline("DET01", state)
        assert bomb_manager._bomb_timer is None


class TestReset:
    def test_reset_clears_all_state(self, conquest_manager: GameManager) -> None:
        conquest_manager.on_sta_activated("STA01", "A", None)
        conquest_manager.on_sta_activated("STA02", "B", None)
        conquest_manager.reset()
        assert conquest_manager.game_state == GameState.IDLE
        assert len(conquest_manager._activated_teams) == 0
        assert len(conquest_manager._eliminated_teams) == 0
        assert len(conquest_manager._sta_team_mapping) == 0
