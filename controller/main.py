import subprocess
import time
import sys
import logging
import os
from pathlib import Path

# from zfj 的项目更改测试

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
import os
from pathlib import Path
import psutil
from logging.handlers import RotatingFileHandler

# 配置日志
log_dir = Path(__file__).parent / "log"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / f"main_{time.strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

# 模块启动顺序
MODULES = [
    "database_process.py",  # 数据库读写模块
    "mqtt_process.py",     # MQTT信息处理模块
    "desktop_app.py",      # 桌面管理端应用
    "game_process.py"      # 游戏逻辑管理和音频生成播放模块
]

# 桌面应用配置（保留原有配置结构）
WEB_HOST = '0.0.0.0'
WEB_PORT = 5000

class ProcessManager:
    def __init__(self):
        self.processes = {}
        self.max_log_size = 1 * 1024 * 1024  # 1MB
        # 使用单一重启计数来源：self.processes[module]['restart_count']
        self.max_restart_attempts = 3

    def _clean_old_logs(self):
        """清理一周前的旧日志文件"""
        try:
            current_time = time.time()
            seven_days_ago = current_time - 7 * 24 * 60 * 60  # 7天前的时间戳
            
            for f in log_dir.glob('*.log'):
                try:
                    file_mtime = os.path.getmtime(f)
                    if file_mtime < seven_days_ago:
                        f.unlink()
                        logger.info(f"删除过期日志文件: {f.name} (修改时间: {time.ctime(file_mtime)})")
                except Exception as e:
                    logger.warning(f"处理日志文件 {f.name} 失败: {str(e)}")
        except Exception as e:
            logger.error(f"清理日志文件失败: {str(e)}")

    def _setup_module_logging(self, module):
        """设置模块日志"""
        module_logger = logging.getLogger(module)
        module_logger.setLevel(logging.DEBUG)  # 设置为最低级别
        
        # 移除模块已有处理器，避免重复
        for handler in module_logger.handlers[:]:
            module_logger.removeHandler(handler)

        log_file = log_dir / f"{module}_{time.strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = RotatingFileHandler(str(log_file), maxBytes=self.max_log_size, backupCount=3, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 使用RotatingFileHandler防止日志无限增长
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        module_logger.addHandler(file_handler)
        # 禁用传播到root，避免重复控制台输出影响主进程日志
        module_logger.propagate = False
        
        # 强制写入测试日志
        module_logger.debug(f"日志系统初始化测试 - {module}")
        module_logger.info(f"模块 {module} 日志系统已配置")
        return module_logger

    def _wait_for_database(self, timeout=30):
        """等待数据库初始化完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 检查数据库文件是否存在
                db_file = Path(__file__).parent / "resource" / "node_status.db"
                if db_file.exists() and db_file.stat().st_size > 0:
                    logger.info("数据库已初始化完成")
                    return True
                time.sleep(1)
            except Exception as e:
                logger.warning(f"检查数据库状态时出错: {str(e)}")
        logger.error("等待数据库初始化超时")
        return False

    def start_module(self, module):
        """启动单个模块"""
        try:
            # 设置模块日志
            self._setup_module_logging(module)
            
            logger.info(f"正在启动模块: {module}")
            # 为子进程创建单独的日志文件，避免使用 PIPE 导致阻塞
            proc_log = log_dir / f"{module}_proc_{time.strftime('%Y%m%d_%H%M%S')}.log"
            fh = open(proc_log, 'a', encoding='utf-8')
            # 设置子进程环境变量
            env = os.environ.copy()
            env['PYTHONPATH'] = str(Path(__file__).parent) + (os.pathsep + env['PYTHONPATH'] if 'PYTHONPATH' in env else '')
            
            # 使用绝对路径执行模块
            module_path = str(Path(__file__).parent / module)
            proc = subprocess.Popen([sys.executable, module_path],
                                  stdout=fh,
                                  stderr=fh,
                                  env=env)
            self.processes[module] = {
                'process': proc,
                'start_time': time.time(),
                'restart_count': 0,
                'last_error': None,
                'log_handle': fh,
                'proc_log_path': str(proc_log)
            }
            
            # 等待模块初始化
            time.sleep(2 if module == "database_process.py" else 1)
            
            if proc.poll() is not None:  # 进程已终止
                # 如果子进程已退出，尝试读取退出码并记录日志文件路径
                return_code = proc.returncode
                error_output = f"退出码: {return_code}, 详情见: {self.processes[module].get('proc_log_path')}"
                logger.error(f"模块 {module} 启动失败: {error_output}")
                self.processes[module]['last_error'] = error_output
                # 关闭子进程日志句柄并清理
                try:
                    fh = self.processes[module].get('log_handle')
                    if fh:
                        fh.close()
                except Exception:
                    pass
                return False
                
            logger.info(f"模块 {module} 已启动 (PID: {proc.pid})")
            return True
        except Exception as e:
            error_msg = f"启动模块 {module} 失败: {str(e)}"
            logger.error(error_msg)
            if module in self.processes:
                self.processes[module]['last_error'] = error_msg
            return False

    def start_all_modules(self):
        """启动所有模块"""
        success = True
        
        # 先启动数据库模块
        if not self.start_module("database_process.py"):
            logger.error("数据库模块启动失败")
            success = False
            
        # 等待数据库初始化完成 (增加超时时间到60秒)
        if not self._wait_for_database(60):
            logger.warning("数据库初始化超时，继续启动其他模块")
            
        # 按顺序启动其他模块
        for module in [m for m in MODULES if m != "database_process.py"]:
            if not self.start_module(module):
                logger.error(f"模块 {module} 启动失败")
                success = False
                continue  # 即使失败也继续尝试启动其他模块
                
        return success

    def stop_module(self, module):
        """停止单个模块"""
        proc_info = self.processes.get(module)
        if not proc_info:
            return False
            
        try:
            # 确保proc_info是字典且包含'process'键
            if not isinstance(proc_info, dict) or 'process' not in proc_info:
                logger.error(f"无效的进程信息结构: {module}")
                return False
                
            proc = proc_info['process']
            # 如果进程已经退出，清理并返回 True
            if hasattr(proc, 'poll') and proc.poll() is not None:
                try:
                    fh = proc_info.get('log_handle')
                    if fh:
                        fh.close()
                except Exception:
                    pass
                # 从进程表中移除已结束进程
                try:
                    self.processes.pop(module, None)
                except Exception:
                    pass
                return True

            # 进程仍在运行，优雅终止 -> 等待 -> 强杀
            if hasattr(proc, 'poll') and proc.poll() is None:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                        logger.info(f"已终止模块 {module} (PID: {proc.pid})")
                    except subprocess.TimeoutExpired:
                        logger.warning(f"模块 {module} 未能在超时内退出，执行强制杀死")
                        proc.kill()
                        proc.wait(timeout=5)
                        logger.info(f"已强制杀死模块 {module} (PID: {proc.pid})")

                    # 关闭子进程日志句柄并移除记录
                    try:
                        fh = proc_info.get('log_handle')
                        if fh:
                            fh.close()
                    except Exception:
                        pass
                    self.processes.pop(module, None)
                    return True
                except Exception as e:
                    logger.error(f"终止模块 {module} 失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"停止模块 {module} 时发生意外错误: {str(e)}")
            return False

    def stop_all_modules(self):
        """停止所有模块"""
        success = True
        for module in list(self.processes.keys()):
            if not self.stop_module(module):
                success = False
        return success

    def restart_module(self, module):
        """重启模块"""
        # 停止并等待清理
        stopped = self.stop_module(module)
        time.sleep(1)
        # 启动新的模块实例
        return self.start_module(module)

    def monitor_modules(self):
        """监控模块状态"""
        try:
            while True:
                self._clean_old_logs()
                
                for module in MODULES:
                    proc_info = self.processes.get(module)
                    if proc_info is None:
                        continue
                        
                    proc = proc_info['process']
                    if proc.poll() is not None:  # 进程已终止
                        return_code = proc.returncode
                        error_output = f"退出码: {return_code}, 详情见: {proc_info.get('proc_log_path')}"
                        proc_info['last_error'] = error_output

                        if proc_info.get('restart_count', 0) < self.max_restart_attempts:
                            logger.warning(f"模块 {module} 异常终止，错误: {error_output[:200]}... 尝试重启...")
                            # 尝试重启（stop_module 会清理已结束的进程条目）
                            if self.restart_module(module):
                                # start_module 会创建新的 proc_info，因此需要检查是否存在再累加
                                if module in self.processes:
                                    self.processes[module]['restart_count'] = proc_info.get('restart_count', 0) + 1
                                    self.processes[module]['last_restart'] = time.time()
                            else:
                                logger.error(f"模块 {module} 重启失败")
                        else:
                            logger.error(f"模块 {module} 重启次数已达上限，系统将退出")
                            self.stop_all_modules()
                            sys.exit(1)
                
                # 检查资源使用情况
                self._check_resource_usage()
                time.sleep(5)  # 每5秒检查一次
                
        except KeyboardInterrupt:
            logger.info("接收到中断信号，正在停止所有模块...")
            self.stop_all_modules()
            logger.info("所有模块已停止")
        except Exception as e:
            logger.critical(f"监控线程发生未处理异常: {str(e)}")
            self.stop_all_modules()
            sys.exit(1)

    def _check_resource_usage(self):
        """检查系统资源使用情况"""
        try:
            # 使用非阻塞采样以避免阻塞监控循环
            cpu_usage = psutil.cpu_percent(interval=None)
            mem_usage = psutil.virtual_memory().percent
            
            if cpu_usage > 90:
                logger.warning(f"CPU使用率过高: {cpu_usage}%")
            if mem_usage > 90:
                logger.warning(f"内存使用率过高: {mem_usage}%")
                
            # 记录各模块资源使用
            for module, proc_info in list(self.processes.items()):
                proc_obj = proc_info.get('process')
                if proc_obj is None:
                    continue
                if proc_obj.poll() is None:  # 进程仍在运行
                    try:
                        proc = psutil.Process(proc_obj.pid)
                        with proc.oneshot():
                            cpu = proc.cpu_percent(interval=None)
                            mem = proc.memory_percent()
                            if cpu > 50 or mem > 10:
                                logger.info(f"模块 {module} 资源使用 - CPU: {cpu}%, 内存: {mem}%")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except Exception as e:
            logger.error(f"检查资源使用失败: {str(e)}")

if __name__ == "__main__":
    manager = ProcessManager()
    logger.info("开始启动系统模块...")
    
    if manager.start_all_modules():
        logger.info("所有模块已启动，开始监控...")
        manager.monitor_modules()
    else:
        logger.error("模块启动失败，系统退出")
        manager.stop_all_modules()
        sys.exit(1)
