from flask import Flask, render_template, jsonify, request
import logging
import sys
from pathlib import Path
from datetime import datetime
import psutil
import time
import threading

# 使用模块本地日志（带轮转）
from pathlib import Path as _Path
from logging_utils import configure_module_logging
logger = configure_module_logging('flask_app', _Path(__file__).parent / 'log')
logger.info("Flask应用模块初始化")

# 引入数据库类型枚举以供查询使用（延迟导入 DatabaseManager 在类内完成以避免循环）
from database_process import DatabaseType

# 初始化Flask
app = Flask(__name__, 
           static_folder=str(Path(__file__).parent / "resource" / "static"),
           template_folder=str(Path(__file__).parent / "resource" / "templates"))

# 全局WebManager实例
_web_manager = None
_web_manager_lock = threading.Lock()

def get_web_manager():
    """获取WebManager单例实例"""
    global _web_manager
    if _web_manager is None:
        with _web_manager_lock:
            if _web_manager is None:
                _web_manager = WebManager()
    return _web_manager

class WebManager:
    def __init__(self):
        self.system_stats = {
            'network': {'status': 'disconnected', 'dBm': 0},
            'cpu_usage': 0,
            'memory_usage': 0
        }
        self.node_stats = []
        self.game_config = None
        self._monitor_thread = None
        # 初始化数据库管理器
        from database_process import DatabaseManager
        self.db_manager = DatabaseManager()
        self._start_stats_monitor()

    def _start_stats_monitor(self):
        """启动系统状态监控线程"""
        def monitor():
            while True:
                self._update_system_stats()
                self.node_stats = self.get_node_status()
                self.game_config = self.get_game_config()
                time.sleep(5)
                
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def _update_system_stats(self):
        """更新系统状态信息"""
        try:
            # 获取CPU和内存使用情况
            cpu_usage = psutil.cpu_percent()
            mem_usage = psutil.virtual_memory().percent
            
            # 获取真实网络状态
            net_status = 'disconnected'
            net_dBm = 0
            if psutil.net_if_stats():
                net_status = 'connected'
                net_dBm =  "功能暂未实现"
            
            # 原子性更新状态
            self.system_stats.update({
                'cpu_usage': cpu_usage,
                'memory_usage': mem_usage,
                'network': {
                    'status': net_status,
                    'dBm': net_dBm
                }
            })
            
        except Exception as e:
            logger.error(f"更新系统状态失败: {str(e)}", exc_info=True)
            # 设置默认状态
            self.system_stats.update({
                'cpu_usage': 0,
                'memory_usage': 0,
                'network': {
                    'status': 'disconnected',
                    'dBm': 0
                }
            })

    def get_game_config(self):
        """获取游戏配置"""
        if not self.db_manager:
            logger.error("数据库管理器未初始化")
            return {
                'team_count': 2,
                'game_mode': 'conquer',
                'game_state': 'unstart',
                'timestamp': datetime.now().isoformat()
            }
            
        result = []
        def callback(response):
            if not response['success']:
                logger.error(f"获取游戏配置失败: {response.get('error', '未知错误')}")
                result.append({
                    'team_count': 2,
                    'game_mode': 'conquer',
                    'game_state': 'unstart',
                    'timestamp': datetime.now().isoformat()
                })
            else:
                try:
                    data = response['data'][0] if response['data'] else None
                    if data:
                        result.append(data)
                    else:
                        result.append({
                            'team_count': 2,
                            'game_mode': 'conquer',
                            'game_state': 'unstart',
                            'timestamp': datetime.now().isoformat()
                        })
                except (KeyError, TypeError, IndexError) as e:
                    logger.error(f"解析游戏配置数据失败: {str(e)}")
                    result.append({
                        'team_count': 2,
                        'game_mode': 'conquer',
                        'game_state': 'unstart',
                        'timestamp': datetime.now().isoformat()
                    })
        
        try:
            self.db_manager.query(
                DatabaseType.GAME_CONFIG,
                "SELECT id, team_count, game_mode, game_state, timestamp FROM game_config ORDER BY id DESC LIMIT 1",
                callback=callback
            )
            # 延长等待时间至5秒
            for _ in range(50):
                if len(result) > 0:
                    break
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"查询游戏配置异常: {str(e)}")
            return {
                'team_count': 2,
                'game_mode': 'conquer',
                'game_state': 'unstart',
                'timestamp': datetime.now().isoformat()
            }
            
        return result[0]

    def update_game_config(self, config):
        """更新游戏配置"""
        if not self.db_manager:
            logger.error("数据库管理器未初始化")
            return False
            
        # 验证数据库连接
        if not self._check_db_connection():
            logger.error("数据库连接不可用")
            return False
            
        success = []
        def callback(response):
            if not response['success']:
                logger.error(f"更新游戏配置失败: {response.get('error', '未知错误')}")
                success.append(False)
            else:
                success.append(response['success'])
        
        try:
            self.db_manager.write(
                DatabaseType.GAME_CONFIG,
                "UPDATE game_config SET team_count=?, game_mode=?, game_state=? WHERE id=?",
                (config['team_count'], config['game_mode'], config['game_state'], config['id']),
                callback=callback
            )
            # 延长等待时间至5秒
            for _ in range(50):
                if len(success) > 0:
                    break
                time.sleep(0.1)
                
            if not success:
                logger.error("更新游戏配置超时")
                return False
                
        except Exception as e:
            logger.error(f"更新游戏配置异常: {str(e)}", exc_info=True)
            return False
            
        return success[0]

    def _check_db_connection(self):
        """检查数据库连接状态"""
        try:
            # 简单查询验证连接
            test_result = []
            def callback(response):
                test_result.append(response['success'])
                
            # 使用与格式化器期望列一致的查询，避免格式化失败
            self.db_manager.query(
                DatabaseType.GAME_CONFIG,
                "SELECT id, team_count, game_mode, game_state, timestamp FROM game_config LIMIT 1",
                callback=callback
            )
            
            # 等待响应
            for _ in range(20):
                if test_result:
                    return test_result[0]
                time.sleep(0.1)
                
            return False
        except Exception as e:
            logger.error(f"数据库连接检查失败: {str(e)}")
            return False

    def _query_node_status(self, callback):
        """执行节点状态查询"""
        logger.info("执行数据库查询: SELECT node_id, online_status, active_status, last_update FROM node_status")
        self.db_manager.query(
            DatabaseType.NODE_STATUS,
            "SELECT node_id, online_status, active_status, last_update FROM node_status",
            callback=callback
        )

    def _process_node_status_response(self, response):
        """处理节点状态查询响应"""
        logger.info(f"收到数据库回调响应: {response}")
        if not response['success']:
            error_msg = response.get('error', '未知错误')
            logger.error(f"获取节点状态失败: {error_msg}")
            return []
            
        try:
            data = response.get('data', [])
            logger.info(f"从数据库获取到原始节点数据，类型: {type(data)}, 内容: {data}")
            
            if not isinstance(data, list):
                logger.error(f"节点状态数据格式错误，应为列表，实际得到: {type(data)}")
                return []
                
            logger.info(f"成功解析节点数据: {len(data)}条记录")
            return data
            
        except Exception as e:
            logger.error(f"解析节点状态数据失败: {str(e)}", exc_info=True)
            return []

    def get_node_status(self):
        """获取所有节点状态"""
        if not self.db_manager:
            logger.error("数据库管理器未初始化")
            return []
            
        logger.info("开始查询节点状态...")
        
        # 验证数据库连接
        logger.info("检查数据库连接...")
        db_connected = self._check_db_connection()
        logger.info(f"数据库连接状态: {'成功' if db_connected else '失败'}")
        if not db_connected:
            logger.error("数据库连接不可用")
            return []
            
        result = []
        def callback(response):
            # 将整个响应结果追加为一个元素，避免扁平化导致后续处理出错
            result.append(self._process_node_status_response(response))
        
        try:
            self._query_node_status(callback)
            
            # 延长等待时间至10秒
            logger.info("等待数据库响应(最多10秒)...")
            for i in range(100):
                if len(result) > 0:
                    logger.info(f"收到数据库响应，等待次数: {i}")
                    break
                time.sleep(0.1)
                
            if not result:
                logger.error("获取节点状态超时，未收到数据库响应")
                return []
                
            nodes = result[0]
            logger.info(f"处理节点数据，共 {len(nodes)} 个节点，首条数据: {nodes[0] if nodes else '无'}")
            
            # 返回原始数据，不转换布尔值
            formatted_nodes = []
            for node in nodes:
                if not isinstance(node, dict):
                    logger.warning(f"忽略无效节点数据格式: {type(node)}, 内容: {node}")
                    continue
                    
                logger.debug(f"处理节点数据: {node}")
                formatted_nodes.append({
                    'node_id': str(node.get('node_id', 'UNKNOWN')),
                    'online_status': int(node.get('online_status', 0)),
                    'active_status': str(node.get('active_status', 'unknown')),
                    'last_update': str(node.get('last_update', '')),
                    'extra_info': str(node.get('extra_info', ''))
                })
                
            logger.info(f"最终返回节点数据: {len(formatted_nodes)} 条")
            return formatted_nodes
            
        except Exception as e:
            logger.error(f"查询节点状态异常: {str(e)}", exc_info=True)
            return []

    def get_log_files(self):
        """获取日志文件列表"""
        log_dir = Path(__file__).parent / "log"
        log_dir.mkdir(exist_ok=True)
        return [f.name for f in log_dir.glob("*.log")]
    
    def get_log_content(self, filename):
        """获取日志文件内容"""
        log_file = Path(__file__).parent / "log" / filename
        if not log_file.exists() or not log_file.is_file():
            return None
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取日志文件失败: {str(e)}")
            return None

    def _format_node_for_api(self, node):
        """格式化节点数据用于API响应（WebManager方法）"""
        if not isinstance(node, dict):
            return None
        
        # 解码active_status
        try:
            active_status = int(node.get('active_status', 0))
        except Exception:
            active_status = 0
        team_mapping = {
            0: '未激活',
            1: 'A队',
            2: 'B队',
            3: 'C队',
            4: 'D队'
        }
        team = team_mapping.get(active_status, '未知')
        
        return {
            'node_id': str(node.get('node_id', '')),
            'online_status': int(node.get('online_status', 0)),
            'active_status': active_status,
            'team': team,
            'last_update': str(node.get('last_update', ''))
        }

# 路由定义
@app.route('/')
def index():
    return render_template('index.html')

# API接口
@app.route('/api/system_stats')
def api_system_stats():
    """获取系统状态"""
    try:
        web_manager = get_web_manager()
        return jsonify(web_manager.system_stats)
    except Exception as e:
        logger.error(f"获取系统状态失败: {str(e)}", exc_info=True)
        return jsonify({'error': '内部服务器错误'}), 500


# 全局API缓存
_api_cache = {}
_api_cache_lock = threading.Lock()

@app.route('/api/node_status')
def api_node_status():
    """获取节点状态"""
    cache_key = 'node_status'
    
    # 检查缓存
    with _api_cache_lock:
        if cache_key in _api_cache and (time.time() - _api_cache[cache_key]['timestamp']) < 1:
            logger.debug("使用缓存的API响应")
            return jsonify(_api_cache[cache_key]['data'])
    
    try:
        web_manager = get_web_manager()
        nodes = web_manager.get_node_status()
        
        # 验证节点数据
        if not isinstance(nodes, list):
            logger.error(f"无效的节点数据格式: {type(nodes)}")
            return jsonify({'error': '数据格式错误'}), 500
            
        # 格式化节点数据并缓存
        formatted_nodes = [web_manager._format_node_for_api(node) for node in nodes]
        formatted_nodes = [node for node in formatted_nodes if node is not None]
        
        with _api_cache_lock:
            _api_cache[cache_key] = {
                'data': formatted_nodes,
                'timestamp': time.time()
            }
            
        return jsonify(formatted_nodes)
        
    except Exception as e:
        logger.error(f"获取节点状态失败: {str(e)}", exc_info=True)
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/update_config', methods=['POST'])
def api_update_config():
    """更新游戏配置"""
    try:
        logger.info("收到更新游戏配置请求")
        if not request.json:
            return jsonify({'success': False, 'error': '缺少请求体'}), 400
            
        web_manager = get_web_manager()
        config = request.json
        
        # 获取当前配置
        current_config = web_manager.get_game_config()
        logger.debug(f"当前配置: {current_config}")
        if not current_config:
            return jsonify({'success': False, 'error': '无法获取当前配置'}), 404
        
        # 更新配置
        update_data = {
            'id': current_config['id'],
            'team_count': config.get('team_count', current_config['team_count']),
            'game_mode': config.get('game_mode', current_config['game_mode']),
            'game_state': config.get('game_state', current_config['game_state'])
        }
        
        success = web_manager.update_game_config(update_data)
        return jsonify({'success': success})
        
    except Exception as e:
        logger.error(f"更新配置失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': '内部服务器错误'}), 500

@app.route('/api/log_files')
def api_log_files():
    """获取日志文件列表"""
    try:
        web_manager = get_web_manager()
        files = web_manager.get_log_files()
        if not isinstance(files, list):
            raise ValueError("日志文件列表格式错误")
        return jsonify(files)
    except Exception as e:
        logger.error(f"获取日志文件列表失败: {str(e)}", exc_info=True)
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/log_content')
def api_log_content():
    """获取日志文件内容"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({'error': '缺少文件名参数'}), 400
        
        web_manager = get_web_manager()
        content = web_manager.get_log_content(filename)
        if content is None:
            return jsonify({'error': '无法读取日志文件'}), 404
        
        return content
    except Exception as e:
        logger.error(f"读取日志内容失败: {str(e)}", exc_info=True)
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/reset_config', methods=['POST'])
def api_reset_config():
    """重置游戏配置到默认值"""
    try:
        web_manager = get_web_manager()
        # 获取默认配置
        default_config = {
            'team_count': 4,
            'game_mode': 'conquer',
            'game_state': 'unstart'
        }
        # 获取当前配置ID
        current_config = web_manager.get_game_config()
        if not current_config:
            return jsonify({'success': False, 'error': '无法获取当前配置'}), 404
        
        # 更新为默认配置
        update_data = {
            'id': current_config['id'],
            'team_count': default_config['team_count'],
            'game_mode': default_config['game_mode'],
            'game_state': default_config['game_state']
        }
        
        success = web_manager.update_game_config(update_data)
        return jsonify({'success': success})
        
    except Exception as e:
        logger.error(f"重置配置失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': '内部服务器错误'}), 500

def run():
    """主运行循环"""
    logger.info("Web管理模块启动")
    try:
        # 启动Flask应用
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except Exception as e:
        logger.error(f"Web模块运行异常: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run()
