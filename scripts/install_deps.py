#!/usr/bin/env python3

import asyncio
import json
import shutil
import tarfile
from pathlib import Path

import httpx


def extract_tar_gz(tar_path: Path, extract_to: Path):
    """使用 Python tarfile 模块提取 .tar.gz 文件"""
    extract_to.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(path=extract_to, filter="data")
    print(f"已成功提取: {tar_path.name} 到 {extract_to}")


async def frp_install(
    arch_name: str, url: str, base_parent: Path, client: httpx.AsyncClient
):
    """异步下载并提取 'frpc' 到目标路径"""
    temp_dir = Path("/tmp/frp_install") / arch_name
    temp_dir.mkdir(parents=True, exist_ok=True)

    tar_path = temp_dir / "pkg.tar.gz"
    extract_dir = temp_dir / "extracted"

    print(f"正在下载 {arch_name}...")
    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(tar_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
    except Exception as e:
        print(f"下载失败 {arch_name}: {e}")
        return

    extract_tar_gz(tar_path, extract_dir)

    found_files = list(extract_dir.rglob("frpc"))
    if not found_files:
        print(f"错误: 在 {arch_name} 的压缩包中未找到 'frpc'")
        return

    frpc_source = found_files[0]
    dest_dir = base_parent.parent / "controller" / "resources" / "frpc" / arch_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    shutil.move(str(frpc_source), str(dest_dir / "frpc"))
    print(f"成功安装: {dest_dir / 'frpc'}")

    shutil.rmtree(temp_dir)


async def frpc_run_installer():
    base_dir = Path(__file__).resolve().parent
    frpc_file = base_dir / "frpc.json"

    if not frpc_file.exists():
        print("错误: 未找到 frpc.json 文件")
        return

    with open(frpc_file, "r", encoding="utf-8") as f:
        frpc = json.load(f)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [frp_install(arch, url, base_dir, client) for arch, url in frpc.items()]
        await asyncio.gather(*tasks)

    print("全部安装完成。")


if __name__ == "__main__":
    asyncio.run(frpc_run_installer())
