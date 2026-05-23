from unittest.mock import MagicMock

import pytest

from controller.src.node_manager import NodeManager, NodeType, OnlineStatus


@pytest.fixture
def node_manager() -> NodeManager:
    event_bus = MagicMock()
    nm = NodeManager(event_bus)
    return nm


class TestNodeManager:
    def test_handle_heartbeat_new_node(self, node_manager: NodeManager) -> None:
        came_online, state = node_manager.handle_heartbeat("STA01")
        assert came_online is True
        assert state.status == OnlineStatus.ONLINE
        assert state.node_id == "STA01"
        assert state.node_type == NodeType.STA

    def test_handle_heartbeat_repeated(self, node_manager: NodeManager) -> None:
        node_manager.handle_heartbeat("STA01")
        _, state = node_manager.handle_heartbeat("STA01")
        assert state.status == OnlineStatus.ONLINE

    def test_handle_activation(self, node_manager: NodeManager) -> None:
        node_manager.handle_heartbeat("DET01")
        state = node_manager.handle_activation("DET01", 1)
        assert state.active_team == "A"

    def test_handle_activation_team_4(self, node_manager: NodeManager) -> None:
        node_manager.handle_heartbeat("DET01")
        state = node_manager.handle_activation("DET01", 4)
        assert state.active_team == "D"

    def test_mark_offline(self, node_manager: NodeManager) -> None:
        node_manager.handle_heartbeat("STA01")
        state = node_manager.mark_offline("STA01")
        assert state.status == OnlineStatus.OFFLINE

    def test_mark_offline_already_offline(self, node_manager: NodeManager) -> None:
        state = node_manager.mark_offline("STA01")
        assert state.status == OnlineStatus.OFFLINE

    def test_reset_node(self, node_manager: NodeManager) -> None:
        node_manager.handle_heartbeat("DET01")
        node_manager.handle_activation("DET01", 2)
        state = node_manager.reset_node("DET01")
        assert state.active_team == ""

    def test_reset_node_not_activated(self, node_manager: NodeManager) -> None:
        node_manager.handle_heartbeat("DET01")
        state = node_manager.reset_node("DET01")
        assert state.active_team == ""

    def test_get_node(self, node_manager: NodeManager) -> None:
        node_manager.handle_heartbeat("STA01")
        state = node_manager.get_node("STA01")
        assert state is not None
        assert state.node_id == "STA01"

    def test_get_node_not_found(self, node_manager: NodeManager) -> None:
        assert node_manager.get_node("NONEXIST") is None

    def test_get_all_nodes(self, node_manager: NodeManager) -> None:
        node_manager.handle_heartbeat("STA01")
        node_manager.handle_heartbeat("DET01")
        all_nodes = node_manager.get_all_nodes()
        assert len(all_nodes) == 2

    def test_infer_node_type_sta(self, node_manager: NodeManager) -> None:
        state = node_manager._get_or_create("STA99")
        assert state.node_type == NodeType.STA

    def test_infer_node_type_det(self, node_manager: NodeManager) -> None:
        state = node_manager._get_or_create("DET99")
        assert state.node_type == NodeType.DET

    def test_infer_node_type_unknown(self, node_manager: NodeManager) -> None:
        state = node_manager._get_or_create("XXX01")
        assert state.node_type == NodeType.UNKNOWN
