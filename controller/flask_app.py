from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
import time
import logging
from pathlib import Path
from logging_utils import configure_module_logging
from database_process import DatabaseManager, DatabaseType

# 配置模块日志
logger = configure_module_logging('flask_app', Path(__file__).parent / 'log')

class WebUtils:
    """Web应用工具函数类"""
    @staticmethod
    def check_db_connection(db_manager):
        """统一数据库连接检查"""
        try:
            test_result = []
            def callback(response):
                test_result.append(response['success'])
                
            db_manager.query(
                DatabaseType.NODE_STATUS,
                "SELECT node_id FROM node_status LIMIT 1",
                callback=callback
            )
            
            for _ in range(30):
                if test_result:
                    return test_result[0]
                time.sleep(0.1)
                
            return False
        except Exception as e:
            logging.error(f"数据库连接检查失败: {str(e)}")
            return False

    @staticmethod
    def format_api_response(data=None, error=None):
        """统一API响应格式"""
        return {
            'success': error is None,
            'data': data,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }

    @staticmethod
    def handle_db_query(db_manager, query, params=None):
        """统一数据库查询处理（线程安全）"""
        import threading
        result = []
        callback_event = threading.Event()
        
        def callback(response):
            if not response['success']:
                logger.error(f"数据库查询失败: {response.get('error', '未知错误')}")
            result.append(response)
            callback_event.set()
            
        db_manager.query(
            DatabaseType.NODE_STATUS,
            query,
            params or (),
            callback=callback
        )
        
        # 等待回调完成或超时
        if not callback_event.wait(timeout=5.0):
            logger.error(f"数据库查询超时: {query}")
            return {'success': False, 'error': '请求超时'}
            
        return result[0] if result else {'success': False, 'error': '未知错误'}

    @staticmethod
    def handle_db_write(db_manager, query, params):
        """统一数据库写入处理（线程安全）"""
        import threading
        success = []
        callback_event = threading.Event()
        
        def callback(response):
            if not response['success']:
                logger.error(f"数据库写入失败: {response.get('error', '未知错误')}")
            success.append(response['success'])
            callback_event.set()
            
        db_manager.write(
            DatabaseType.NODE_STATUS,
            query,
            params,
            callback=callback
        )
        
        # 等待回调完成或超时
        if not callback_event.wait(timeout=5.0):
            logger.error(f"数据库写入超时: {query}")
            return False
            
        return success[0] if success else False

def main():
    """标准模块入口函数"""
    from database_process import DatabaseManager
    db_manager = DatabaseManager()
    app = create_app(db_manager)
    app.run(host='0.0.0.0', port=5000)

def create_app(db_manager):
    """创建Flask应用"""
    app = Flask(__name__, 
               static_folder='resource/static',
               template_folder='resource/templates')
    # 简单配置
    app.config['HOST'] = '0.0.0.0'
    app.config['PORT'] = 5000
    app.config['DB_MANAGER'] = db_manager

    @app.route('/')
    def index():
        """返回前端页面"""
        return send_from_directory(app.template_folder, 'index.html')
    
    # API路由
    @app.route('/api/status', methods=['GET'])
    def get_status():
        """获取系统状态"""
        try:
            # 获取所有节点状态(STA01-STA04, DET01-DET06)
            nodes = []
            # 查询STA节点
            for i in range(1, 5):
                node_id = f"STA{i:02d}"
                result = WebUtils.handle_db_query(
                    db_manager,
                    "SELECT * FROM node_status WHERE node_id=?",
                    (node_id,)
                )
                if result['success'] and result['data']:
                    nodes.append(result['data'][0])
            
            # 查询DET节点
            for i in range(1, 7):
                node_id = f"DET{i:02d}"
                result = WebUtils.handle_db_query(
                    db_manager,
                    "SELECT * FROM node_status WHERE node_id=?",
                    (node_id,)
                )
                if result['success'] and result['data']:
                    nodes.append(result['data'][0])
            
            return jsonify(WebUtils.format_api_response({
                'nodes': nodes,
                'system': {
                    'cpu': 0,  # 待实现
                    'memory': 0,  # 待实现
                    'network': 'connected'  # 待实现
                }
            }))
        except Exception as e:
            logger.error(f"获取状态失败: {str(e)}")
            return jsonify(WebUtils.format_api_response(error=str(e)))
    
    @staticmethod
    def _execute_db_operation(db_manager, operation_type, query, params=None, timeout=3.0):
        """执行数据库操作并等待结果"""
        import threading
        result = None
        callback_event = threading.Event()
        
        def callback(response):
            nonlocal result
            logger.debug(f"收到数据库{operation_type}操作回调: {response}")
            result = response
            callback_event.set()
            
        if operation_type == 'query':
            db_manager.query(DatabaseType.GAME_CONFIG, query, params or (), callback=callback)
        else:
            db_manager.write(DatabaseType.GAME_CONFIG, query, params or (), callback=callback)
            
        if not callback_event.wait(timeout=timeout):
            logger.warning(f"数据库{operation_type}操作超时")
            return None
            
        return result

    @app.route('/api/config', methods=['GET', 'POST'])
    def handle_config():
        """配置功能(待完善)"""
        return jsonify(WebUtils.format_api_response(
            error="功能开发中，敬请期待"
        ))
    
    @app.route('/api/logs', methods=['GET'])
    def get_logs():
        """获取日志列表"""
        try:
            # 待实现：读取日志文件列表
            return jsonify(WebUtils.format_api_response(data=[]))
        except Exception as e:
            logger.error(f"获取日志失败: {str(e)}")
            return jsonify(WebUtils.format_api_response(error=str(e)))
    
    return app

if __name__ == "__main__":
    """独立运行模式"""
    import sys
    from database_process import DatabaseManager
    
    # 初始化数据库管理器
    db_manager = DatabaseManager()
    
    # 创建并运行应用
    app = create_app(db_manager)
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=False
    )
