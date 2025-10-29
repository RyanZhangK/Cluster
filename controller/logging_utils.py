import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time

def configure_module_logging(module_name: str, log_dir: Path, max_bytes: int = 1 * 1024 * 1024, backup_count: int = 3):
    """为模块配置带轮转的文件日志。

    - module_name: 文件/记录器命名前缀
    - log_dir: 日志目录路径（Path）
    - max_bytes, backup_count: 轮转配置
    返回 module logger
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)

    # 移除已有 handler
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    timestamp = time.strftime('%Y%m%d')
    log_file = log_dir / f"{module_name}.log"
    handler = RotatingFileHandler(str(log_file), maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

    # 不向父 logger 传播，避免重复输出
    logger.propagate = False
    logger.debug(f"模块 {module_name} 日志已初始化 (path={log_file})")
    return logger
