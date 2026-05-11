#!/usr/bin/env python3
"""
MQTT 测试消息发送脚本
用于模拟 ESP8266 节点发送心跳和激活消息
"""

import asyncio
import sys
from pathlib import Path

# 添加 src 目录到 path，便于导入 config
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import aiomqtt
from config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_SUB


async def send_message(payload: str) -> None:
    """发送单条消息到 MQTT broker。"""
    try:
        async with aiomqtt.Client(MQTT_BROKER, MQTT_PORT) as client:
            await client.publish(MQTT_TOPIC_SUB, payload, qos=1)
            print(f"✓ 已发送: {payload}")
    except Exception as e:
        print(f"✗ 发送失败: {e}")
        sys.exit(1)


def show_menu() -> None:
    """显示菜单。"""
    print("\n" + "=" * 50)
    print("MQTT 测试消息发送工具")
    print("=" * 50)
    print("\n预设消息:")
    print("  1. STA01 心跳")
    print("  2. STA02 心跳")
    print("  3. DET01 心跳")
    print("  4. DET01 激活队伍 A")
    print("  5. DET01 激活队伍 B")
    print("  6. DET01 激活队伍 C")
    print("  7. DET01 激活队伍 D")
    print("  8. 自定义消息")
    print("  9. 所有")
    print("  0. 退出")
    print()


def get_preset_message(choice: str) -> str | None:
    """根据选择返回预设消息。"""
    presets = {
        "1": "STA01H0",
        "2": "STA02H0",
        "3": "DET01H0",
        "4": "DET01AA",
        "5": "DET01AB",
        "6": "DET01AC",
        "7": "DET01AD",
    }
    return presets.get(choice)


async def main() -> None:
    """主循环。"""
    print(f"连接到 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"发布主题: {MQTT_TOPIC_SUB}")

    while True:
        show_menu()
        choice = input("请选择 (0-8): ").strip()

        match choice:
            case "0":
                print("退出")
                break
            case "9":
                for i in range(1, 8):
                    payload = get_preset_message(str(i))
                    assert payload is not None, "Payload should not be None"
                    await send_message(payload)
                continue
            case "8":
                payload = input("输入消息 (7字节 ASCII): ").strip()
                if len(payload) != 7:
                    print(f"✗ 消息长度错误: 期望 7 字节，实际 {len(payload)}")
                    continue
            case _:
                payload = get_preset_message(choice)
                if payload is None:
                    print("✗ 无效选择")
                    continue
        await send_message(payload)


if __name__ == "__main__":
    asyncio.run(main())
