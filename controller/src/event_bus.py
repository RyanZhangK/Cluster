from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """
    全局事件总线，作为单例在各模块间传递。
    所有 Signal 均在 GUI 线程（qasync 主线程）中 emit，
    无需 Qt.QueuedConnection，默认 DirectConnection 即可。
    """

    # MQTT Broker 连接成功（主控系统上线）
    mqtt_connected = Signal()

    # 任何状态变更均 emit（心跳刷新、激活、上下线）
    # 参数: node_id: str, state: NodeState
    node_status_changed = Signal(str, object)

    # 节点从 OFFLINE → ONLINE（仅在状态跃迁时 emit）
    # 参数: node_id: str, state: NodeState
    node_came_online = Signal(str, object)

    # 节点心跳超时 → OFFLINE
    # 参数: node_id: str, state: NodeState
    node_went_offline = Signal(str, object)

    # 节点收到激活消息
    # 参数: node_id: str, team: str (A/B/C/D), state: NodeState
    node_activated = Signal(str, str, object)

    # 节点状态被手动重置（来自 UI 操作）
    # 参数: node_id: str, state: NodeState
    node_reset = Signal(str, object)

    # 游戏事件信号
    game_started = Signal()
    team_eliminated = Signal(str)  # team: str (A/B/C/D)
    team_victory = Signal(str)  # team: str
    bomb_activated = Signal()
    bomb_defused = Signal()
    bomb_exploded = Signal()
    bomb_tick = Signal(int)  # 倒计时剩余秒数
