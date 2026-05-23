#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def step(msg: str) -> None:
    print(f"\n==> {msg}")


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"    $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT)
    if result.returncode != 0:
        print(f"    [失败] 返回码 {result.returncode}")
        sys.exit(result.returncode)


def main() -> None:
    step("1/4 检查 Python 版本...")
    py_version = sys.version_info[:2]
    py_expected = (3, 12)
    if py_version != py_expected:
        print(
            f"    需要 Python {py_expected[0]}.{py_expected[1]}，当前是 {py_version[0]}.{py_version[1]}"
        )
        print("    请使用 uv python pin 或 pyenv 切换版本。")
        sys.exit(1)
    print(f"    Python {py_version[0]}.{py_version[1]} ✓")

    step("2/4 同步 Python 依赖...")
    run(["uv", "sync", "--locked"])

    step("3/4 安装 pre-commit hooks...")
    run(["uv", "run", "pre-commit", "install"])

    step("4/4 下载依赖文件...")
    install_deps = PROJECT_ROOT / "scripts" / "install_deps.py"
    if install_deps.exists():
        run(["uv", "run", str(install_deps)])
    else:
        print("    未找到 scripts/install_deps.py，跳过。")


if __name__ == "__main__":
    main()
