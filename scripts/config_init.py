#!/usr/bin/env python3

import argparse
import os
import tomllib
from pathlib import Path

from pydantic_settings import BaseSettings

from controller.src.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEV_CONFIG_PATH = PROJECT_ROOT / "config.toml"
USER_CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cluster"
)
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.toml"


# 单一事实来源：直接从 pydantic Settings 模型生成默认配置
# 只读字段声明里的默认值，不实例化子模型：子模型的 default_factory 会触发
# BaseSettings 初始化，而子模型本身没设 env_prefix，会把构建机上 DEV / PORT
# 这类无前缀环境变量读进来，烤进生成的“默认”配置里。
def _section_defaults(model: type[BaseSettings]) -> dict[str, object]:
    """取单个配置节的字段默认值（该层的字段都是标量）"""
    defaults: dict[str, object] = {}
    for name, field in model.model_fields.items():
        if field.default_factory is not None:
            defaults[name] = field.default_factory()
        else:
            defaults[name] = field.default
    return defaults


def _declared_defaults(model: type[BaseSettings]) -> dict[str, dict[str, object]]:
    """展开顶层 Settings：每个字段对应一个配置节"""
    config: dict[str, dict[str, object]] = {}
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseSettings):
            config[name] = _section_defaults(annotation)
    return config


DEFAULT_CONFIG: dict[str, dict[str, object]] = _declared_defaults(Settings)


def toml_dumps_value(val: object) -> str:
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, str):
        return f'"{val}"'
    return str(val)


def _target_path(output: Path | None, user: bool) -> Path:
    if output is not None:
        return output
    return USER_CONFIG_PATH if user else DEV_CONFIG_PATH


def generate(
    force: bool = False, user: bool = False, output: Path | None = None
) -> None:
    """生成带注释的完整 config.toml"""
    path = _target_path(output, user)

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

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"已生成: {path}")


def validate(user: bool = False, output: Path | None = None) -> bool:
    """校验现有 config.toml 是否合法"""
    path = _target_path(output, user)

    if not path.exists():
        print(f"错误: 未找到配置文件: {path}")
        return False

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
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
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--user",
        action="store_true",
        help="写入用户配置目录 (~/.config/cluster/config.toml)",
    )
    target.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="写入指定路径（打包流程用）",
    )
    args = parser.parse_args()

    if args.validate:
        validate(user=args.user, output=args.output)
    else:
        generate(force=args.force, user=args.user, output=args.output)
        print()
        validate(user=args.user, output=args.output)


if __name__ == "__main__":
    main()
