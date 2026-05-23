#!/usr/bin/env python3

import argparse
from pathlib import Path

import toml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.toml"

DEFAULT_CONFIG = {
    "mqtt": {
        "broker": "127.0.0.1",
        "port": 1883,
        "qos": 1,
        "topic_sub": "node/status",
        "topic_pub": "node/{node_id}/status",
    },
    "broker": {
        "enabled": True,
        "bind_host": "0.0.0.0",
        "bind_port": 1883,
    },
    "game": {
        "heartbeat_timeout": 600,
        "watchdog_interval": 30,
    },
    "controller": {
        "dev": False,
        "ui_hot_reload": False,
    },
    "message": {
        "msg_length": 7,
        "node_id_length": 5,
    },
    "frpc": {
        "server_addr": "",
        "server_port": 7000,
        "auth_token": "",
        "proxies": "[]",
    },
}


def toml_dumps_value(val: object) -> str:
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, str):
        return f'"{val}"'
    return str(val)


def generate(force: bool = False) -> None:
    """生成带注释的完整 config.toml"""
    lines = [""]

    for section, values in DEFAULT_CONFIG.items():
        lines.append(f"[{section}]")
        for key, val in values.items():
            lines.append(f"    {key} = {toml_dumps_value(val)}")

        lines.append("")

    content = "\n".join(lines)

    if CONFIG_PATH.exists():
        existing = CONFIG_PATH.read_text(encoding="utf-8").strip()
        non_comment = [
            line
            for line in existing.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if non_comment and not force:
            print("config.toml 已存在且有有效配置，跳过（使用 --force 覆盖）。")
            return
        if non_comment and force:
            print("config.toml 已存在，--force 覆盖。")

    CONFIG_PATH.write_text(content, encoding="utf-8")
    print(f"已生成: {CONFIG_PATH}")


def validate() -> bool:
    """校验现有 config.toml 是否合法"""
    if not CONFIG_PATH.exists():
        print(f"错误: 未找到配置文件: {CONFIG_PATH}")
        return False

    try:
        data = toml.load(CONFIG_PATH)
    except Exception as e:
        print(f"错误: config.toml 解析失败: {e}")
        return False

    ok = True

    for section, fields in DEFAULT_CONFIG.items():
        if section not in data:
            print(f"  [缺失] [{section}] 整个节缺失，将使用默认值")
            ok = False
            continue

        for key in fields:
            if key not in data[section]:
                print(f"  [缺失] [{section}] {key} 缺失，将使用默认值: {fields[key]}")
                ok = False

    known_sections = set(DEFAULT_CONFIG.keys())
    for section in data:
        if section not in known_sections:
            print(f"  [警告] 未知配置节 [{section}]，将被忽略")

    if ok:
        print("config.toml 校验通过 ✓")
    else:
        print("config.toml 存在缺失项（将使用默认值补全）")

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="配置初始化/校验工具")
    parser.add_argument("--validate", action="store_true", help="校验现有配置而不生成")
    parser.add_argument("--force", action="store_true", help="强制覆盖已有文件")
    args = parser.parse_args()

    if args.validate:
        validate()
    else:
        generate(force=args.force)
        print()
        validate()


if __name__ == "__main__":
    main()
