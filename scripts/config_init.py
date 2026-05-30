#!/usr/bin/env python3

import argparse
import os
from pathlib import Path

import toml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEV_CONFIG_PATH = PROJECT_ROOT / "config.toml"
USER_CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cluster"
)
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.toml"

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


def generate(force: bool = False, user: bool = False) -> None:
    """生成带注释的完整 config.toml"""
    path = USER_CONFIG_PATH if user else DEV_CONFIG_PATH

    lines = [""]

    for section, values in DEFAULT_CONFIG.items():
        lines.append(f"[{section}]")
        for key, val in values.items():
            lines.append(f"    {key} = {toml_dumps_value(val)}")

        lines.append("")

    content = "\n".join(lines)

    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        non_comment = [
            line
            for line in existing.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if non_comment and not force:
            print(f"{path} 已存在且有有效配置，跳过（使用 --force 覆盖）。")
            return
        if non_comment and force:
            print(f"{path} 已存在，--force 覆盖。")

    if user:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"已生成: {path}")


def validate(user: bool = False) -> bool:
    """校验现有 config.toml 是否合法"""
    path = USER_CONFIG_PATH if user else DEV_CONFIG_PATH

    if not path.exists():
        print(f"错误: 未找到配置文件: {path}")
        return False

    try:
        data = toml.load(path)
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
    parser.add_argument(
        "--user",
        action="store_true",
        help="写入用户配置目录 (~/.config/cluster/config.toml)",
    )
    args = parser.parse_args()

    if args.validate:
        validate(user=args.user)
    else:
        generate(force=args.force, user=args.user)
        print()
        validate(user=args.user)


if __name__ == "__main__":
    main()
