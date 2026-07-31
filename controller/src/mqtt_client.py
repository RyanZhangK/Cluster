import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import aiomqtt

from .config import (
    BROKER_READY,
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_QOS,
    MQTT_TOPIC_SUB,
    MSG_LENGTH,
    NODE_ID_LENGTH,
)

if TYPE_CHECKING:
    from event_bus import EventBus
    from node_manager import NodeManager

logger = logging.getLogger(__name__)

# DET 节点固件 bug 兼容：extra_info 可能为 A-D 或 1-4
# 内存中统一存储为 A-D
TEAM_MAP = {"1": 1, "2": 2, "3": 3, "4": 4, "A": 1, "B": 2, "C": 3, "D": 4}


class MessageParseError(ValueError):
    """消息解析错误。"""


def parse_message(raw: str) -> tuple[str, str, int]:
    """
    解析 7 字节 ASCII 消息。
    返回 (node_id: str, action_type: str, team_or_zero: int)
      - 心跳：team_or_zero = 0
      - 激活：team_or_zero = 1..4
    抛出 MessageParseError 处理所有无效输入。
    """
    if len(raw) != MSG_LENGTH:
        raise MessageParseError(f"消息长度错误: 期望 {MSG_LENGTH}，实际 {len(raw)}")

    node_id = raw[:NODE_ID_LENGTH]
    action_type = raw[NODE_ID_LENGTH]
    extra_info = raw[NODE_ID_LENGTH + 1]

    if action_type not in ("H", "A"):
        raise MessageParseError(f"无效的动作类型: {action_type!r}")

    if action_type == "H":
        if extra_info != "0":
            raise MessageParseError(
                f"心跳消息 extra_info 必须为 '0'，实际 {extra_info!r}"
            )
        return node_id, action_type, 0

    else:
        if extra_info not in TEAM_MAP:
            raise MessageParseError(f"无效的队伍编号: {extra_info!r}")
        team = TEAM_MAP[extra_info]
        return node_id, action_type, team


class MQTTClient:
    def __init__(self, node_manager: "NodeManager", event_bus: "EventBus") -> None:
        self._node_manager = node_manager
        self._event_bus = event_bus
        self._publish_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

    def publish(self, topic: str, payload: str) -> None:
        """入队发布请求。可从 Qt 主线程同步调用，不阻塞 UI。"""
        self._publish_queue.put_nowait((topic, payload))

    async def _publish_worker(self, client: aiomqtt.Client) -> None:
        """从队列取出消息并通过 MQTT 发布。"""
        while True:
            topic, payload = await self._publish_queue.get()
            try:
                await client.publish(topic, payload, qos=MQTT_QOS)
                logger.info(f"Published to {topic}: {payload}")
            except aiomqtt.MqttError as e:
                logger.error(f"Failed to publish to {topic}: {e}")
            except Exception:
                logger.exception(f"Unexpected error publishing to {topic}")

    async def run(self) -> None:
        """
        主循环：连接 Broker → 订阅 → 持续接收消息。
        连接失败时等待 5 秒后重试，永不退出。
        """
        try:
            async with asyncio.timeout(5):
                await BROKER_READY.wait()
        except TimeoutError as e:
            logger.warning(f"MQTT 连接超时: {e}")

        while True:
            try:
                async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
                    logger.info(f"已连接到 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
                    self._event_bus.mqtt_connected.emit()
                    await client.subscribe(MQTT_TOPIC_SUB, qos=MQTT_QOS)
                    logger.info(f"已订阅主题: {MQTT_TOPIC_SUB}")

                    publish_task = asyncio.create_task(
                        self._publish_worker(client), name="mqtt_publish_worker"
                    )
                    try:
                        async for message in client.messages:
                            await self._handle_message(message)
                    finally:
                        publish_task.cancel()
                        try:
                            await publish_task
                        except asyncio.CancelledError:
                            pass
            except aiomqtt.MqttError as e:
                logger.error(f"MQTT 连接错误: {e}，5 秒后重试...")
                await asyncio.sleep(5)
            except Exception as e:  # noqa: BLE001 - 连接循环兜底，保持重试
                logger.error(f"未预期的错误: {e}，5 秒后重试...")
                await asyncio.sleep(5)

    async def _handle_message(self, message: aiomqtt.Message) -> None:
        """
        解码 payload → 调用 parse_message →
        分发给 NodeManager → emit EventBus 信号。
        解析失败仅记录警告，不中断循环。
        """
        try:
            raw_payload = message.payload.decode("utf-8", errors="replace")
            timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
            self._event_bus.mqtt_message_received.emit(
                MQTT_TOPIC_SUB, raw_payload, timestamp
            )
            node_id, action_type, team_or_zero = parse_message(raw_payload)

            if action_type == "H":
                came_online, _ = self._node_manager.handle_heartbeat(node_id)
                if came_online:
                    logger.info(f"节点 {node_id} 上线")

            elif action_type == "A":
                self._node_manager.handle_activation(node_id, team_or_zero)

        except MessageParseError as e:
            logger.warning(f"消息解析失败: {e}，原始 payload: {message.payload!r}")
        except Exception as e:  # noqa: BLE001 - 单条消息兜底，不中断消息循环
            logger.error(f"处理消息时出错: {e}，原始 payload: {message.payload!r}")
