import sqlite3
from pathlib import Path as _Path
from logging import getLogger as _getLogger
from logging_utils import configure_module_logging
import time
#import logging
import sys
import queue
import threading
from pathlib import Path
from enum import Enum

# 使用模块本地日志（带轮转）
logger = configure_module_logging('database_process', _Path(__file__).parent / 'log')

# 数据库枚举
class DatabaseType(Enum):
    NODE_STATUS = 1
    GAME_CONFIG = 2

# 数据库配置
DB_PATHS = {
    DatabaseType.NODE_STATUS: Path(__file__).parent / "resource" / "node_status.db",
    DatabaseType.GAME_CONFIG: Path(__file__).parent / "resource" / "game_config.db"
}

# 节点配置
NODE_IDS = [f"STA{i:02d}" for i in range(1, 5)] + [f"DET{i:02d}" for i in range(1, 7)]

class DatabaseManager:
    def __init__(self):
        self.connections = {}
        self.query_queue = queue.Queue()
        self.write_queue = queue.Queue()
        # 初始化数据库文件/表（使用临时连接完成初始化）
        self._init_databases()

        # 线程停止事件与线程列表
        self._stop_event = threading.Event()
        self.worker_threads = []

        # 启动数据库工作线程（每个线程创建自己的连接）
        self._start_workers()

    def _init_databases(self):
        """初始化所有数据库"""
        try:
            # 初始化节点状态数据库（使用临时连接，避免跨线程共享连接对象）
            node_db_path = DB_PATHS[DatabaseType.NODE_STATUS]

            with sqlite3.connect(node_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS node_status (
                        node_id TEXT PRIMARY KEY,
                        online_status INTEGER DEFAULT 0,
                        active_status INTEGER DEFAULT 0,
                        activator TEXT DEFAULT NULL,
                        last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 只插入不存在的节点，不覆盖已有节点状态
                existing_nodes = [row[0] for row in cursor.execute(
                    "SELECT node_id FROM node_status"
                ).fetchall()]
                
                new_nodes = [node_id for node_id in NODE_IDS if node_id not in existing_nodes]
                
                if new_nodes:
                    cursor.executemany(
                        "INSERT OR IGNORE INTO node_status (node_id) VALUES (?)",
                        [(node_id,) for node_id in new_nodes]
                    )
                    logger.info(f"初始化了 {len(new_nodes)} 个新节点")
                
                conn.commit()

            # 初始化游戏配置数据库（单记录模式）
            game_db_path = DB_PATHS[DatabaseType.GAME_CONFIG]
            with sqlite3.connect(game_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS game_config (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        team_count INTEGER DEFAULT 2,
                        game_mode TEXT DEFAULT 'conquer',
                        game_state TEXT DEFAULT 'unstart',
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
#                cursor.execute('''
#                    INSERT OR REPLACE INTO game_config (id, team_count, game_mode, game_state)
#                    VALUES (1, 2, 'conquer', 'unstart')
#                ''')
                conn.commit()

            logger.info("所有数据库初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}")
            raise

    def _db_worker(self):
        """数据库工作线程：每个线程创建自己的连接并使用阻塞队列获取任务"""
        # 为当前线程创建独立连接
        local_conns = {}
        try:
            for db_type, path in DB_PATHS.items():
                # 每个线程只在本线程中使用这些连接
                local_conns[db_type] = sqlite3.connect(path)
        except Exception as e:
            logger.error(f"为数据库工作线程创建连接失败: {e}")
            return

        # 主循环：使用阻塞式 get()，响应停止事件
        while not self._stop_event.is_set():
            # 处理查询请求（阻塞式，带超时以便检查停止事件）
            try:
                query = self.query_queue.get(timeout=0.5)
            except queue.Empty:
                query = None

            if query:
                try:
                    logger.debug(f"处理查询 SQL: {query.get('sql')} params: {query.get('params')}")
                    conn = local_conns.get(query['db_type'])
                    if not conn:
                        raise Exception(f"数据库连接不存在: {query['db_type']}")
                    cursor = conn.cursor()
                    cursor.execute(query['sql'], query.get('params', ()))
                    result = cursor.fetchall()
                    # 回调采用统一的 wrapped_callback 来格式化
                    query['callback'](result, None)
                except Exception as e:
                    try:
                        query['callback'](None, str(e))
                    except Exception:
                        pass
                finally:
                    try:
                        self.query_queue.task_done()
                    except Exception:
                        pass

            # 处理写入请求
            try:
                write = self.write_queue.get(timeout=0.5)
            except queue.Empty:
                write = None

            if write:
                conn = None
                try:
                    logger.debug(f"处理写入 SQL: {write.get('sql')} params: {write.get('params')}")
                    conn = local_conns.get(write['db_type'])
                    if not conn:
                        raise Exception(f"数据库连接不存在: {write['db_type']}")
                    cursor = conn.cursor()
                    cursor.execute(write['sql'], write.get('params', ()))
                    conn.commit()
                    try:
                        write['callback'](True, None)
                    except Exception:
                        pass
                except Exception as e:
                    # 仅当 conn 非 None 时回滚
                    try:
                        if conn is not None:
                            conn.rollback()
                    except Exception:
                        pass
                    try:
                        write['callback'](False, str(e))
                    except Exception:
                        pass
                finally:
                    try:
                        self.write_queue.task_done()
                    except Exception:
                        pass

        # 线程退出前关闭本地连接
        for c in local_conns.values():
            try:
                c.close()
            except Exception:
                pass

    def _start_workers(self):
        """启动数据库工作线程"""
        for _ in range(2):  # 启动2个工作线程
            worker = threading.Thread(target=self._db_worker, daemon=True)
            worker.start()
            self.worker_threads.append(worker)

    def _format_response(self, data, db_type):
        """格式化数据库响应"""
        if db_type == DatabaseType.NODE_STATUS:
            return {
                'success': True,
                'data': [{
                    'node_id': row[0],
                    'online': bool(row[1]),
                    'active': bool(row[2]),
                    'last_update': row[3]
                } for row in data],
                'timestamp': time.time()
            }
        elif db_type == DatabaseType.GAME_CONFIG:
            return {
                'success': True,
                'data': [{
                    'id': row[0],
                    'team_count': int(row[1]),
                    'game_mode': str(row[2]),
                    'game_state': str(row[3]),
                    'timestamp': str(row[4])
                } for row in data] if data else [],
                'timestamp': time.time()
            }
        return {'success': True, 'data': data, 'timestamp': time.time()}

    def _format_error(self, error):
        """格式化错误响应"""
        return {
            'success': False,
            'error': str(error),
            'timestamp': time.time()
        }

    def query(self, db_type, sql, params=(), callback=None):
        """异步查询数据库"""
        def wrapped_callback(data, error):
            # 首先构建统一的 response 对象
            if error:
                response = self._format_error(error)
            else:
                try:
                    response = self._format_response(data, db_type)
                except Exception as e:
                    # 如果格式化响应失败，返回错误响应而不是抛出异常
                    response = self._format_error(str(e))

            if not callback:
                return

            # 一些调用者使用两参数回调 (result, error)，有些使用单参数(response)
            try:
                # 先尝试以单参数(response)方式调用
                callback(response)
            except TypeError:
                # 回退到旧式签名 (data, error)
                try:
                    callback(data, error)
                except Exception:
                    # 最后兜底：直接调用并忽略错误
                    try:
                        callback(response)
                    except Exception:
                        pass
            
        self.query_queue.put({
            'db_type': db_type,
            'sql': sql,
            'params': params,
            'callback': wrapped_callback
        })

    def write(self, db_type, sql, params=(), callback=None):
        """异步写入数据库"""
        def wrapped_callback(success, error):
            response = {
                'success': success,
                'timestamp': time.time()
            }
            if error:
                response['error'] = str(error)
            callback(response) if callback else None
            
        self.write_queue.put({
            'db_type': db_type,
            'sql': sql,
            'params': params,
            'callback': wrapped_callback
        })

    def run(self):
        """主运行循环"""
        logger.info("数据库模块启动")
        try:
            # 初始检查数据库连接
            for db_type in DatabaseType:
                if not self.connections.get(db_type):
                    self._init_databases()
                    break
            
            # 主循环仅用于保持进程运行
            while True:
                time.sleep(60)  # 延长检查间隔到60秒
                # 仅在检测到连接异常时才重新初始化
                try:
                    for db_type, conn in self.connections.items():
                        if conn and conn.execute("SELECT 1").fetchone()[0] != 1:
                            logger.warning(f"数据库 {db_type} 连接异常，尝试重新初始化")
                            self._init_databases()
                            break
                except Exception:
                    logger.warning("数据库连接检查失败，尝试重新初始化")
                    self._init_databases()
                    
        except KeyboardInterrupt:
            logger.info("接收到中断信号，停止数据库模块")
            self._stop_event.set()
        except Exception as e:
            logger.error(f"数据库模块运行异常: {str(e)}")
            sys.exit(1)
        finally:
            for conn in self.connections.values():
                if conn:
                    conn.close()

if __name__ == "__main__":
    try:
        db_manager = DatabaseManager()
        
        # 测试查询节点状态
        def query_node_callback(result, error):
            if error:
                logger.error(f"查询节点状态失败: {error}")
            else:
                logger.info(f"节点状态查询结果: {result}")
                 # 打印详细状态
                if result and result.get('data'):
                    for node in result['data']:
                        logger.info(f"节点ID: {node['node_id']}, 在线状态: {node['online']}, 活跃状态: {node['active']}, 上次更新时间: {node['last_update']}")
        
        db_manager.query(
            DatabaseType.NODE_STATUS,
            "SELECT * FROM node_status",
            callback=query_node_callback
        )

        # 定义更新游戏配置的回调函数
        def write_game_config_callback(response):
            if response['success']:
                logger.info("游戏配置更新成功")
            else:
                logger.error(f"游戏配置更新失败: {response['error']}")

        # 执行写入操作
        db_manager.write(
            DatabaseType.GAME_CONFIG,  # 数据库类型
            "UPDATE game_config SET team_count = ?, game_mode = ?, game_state = ? WHERE id = 1",  # SQL更新语句
            (3, 'conquer', 'unstart'),  # 更新参数
            callback=write_game_config_callback  # 回调函数
        )   



        # 测试查询游戏配置
        def query_game_config_callback(result, error):
            if error:
                logger.error(f"查询游戏配置失败: {error}")
            else:
                logger.info(f"游戏配置查询结果: {result}")
                # 打印详细配置
                if result and result.get('data'):
                    config = result['data'][0]
                    logger.info(f"当前游戏配置: 队伍数={config['team_count']}, 模式={config['game_mode']}, 状态={config['game_state']}")
        
        db_manager.query(
            DatabaseType.GAME_CONFIG,
            "SELECT * FROM game_config",
            callback=query_game_config_callback
        )
        
        db_manager.run()
    except Exception as e:
        logger.error(f"数据库模块初始化失败: {str(e)}")
        sys.exit(1)

