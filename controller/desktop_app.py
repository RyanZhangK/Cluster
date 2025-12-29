import sys
import time
import threading
from datetime import datetime
from pathlib import Path
import logging
from logging_utils import configure_module_logging

# PySide6 imports
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QTabWidget, QLabel, QPushButton, 
                               QComboBox, QFormLayout, QGroupBox, QTextEdit,
                               QGridLayout, QProgressBar, QMessageBox, QScrollArea)
from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtGui import QFont, QPalette, QColor

# 数据库相关导入
from database_process import DatabaseManager, DatabaseType

# 配置模块日志
logger = configure_module_logging('desktop_app', Path(__file__).parent / 'log')

class DatabaseWorker(QThread):
    """数据库工作线程"""
    query_result = Signal(dict)
    write_result = Signal(dict)
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.query_queue = []
        self.write_queue = []
        self.running = True
        
    def add_query(self, db_type, sql, params=()):
        """添加查询任务"""
        self.query_queue.append({
            'db_type': db_type,
            'sql': sql,
            'params': params
        })
        
    def add_write(self, db_type, sql, params=()):
        """添加写入任务"""
        self.write_queue.append({
            'db_type': db_type,
            'sql': sql,
            'params': params
        })
        
    def run(self):
        """运行工作线程"""
        while self.running:
            # 处理查询任务
            if self.query_queue:
                task = self.query_queue.pop(0)
                try:
                    result = []
                    callback_event = threading.Event()
                    
                    def callback(response):
                        result.append(response)
                        callback_event.set()
                        
                    self.db_manager.query(
                        task['db_type'],
                        task['sql'],
                        task['params'],
                        callback=callback
                    )
                    
                    if callback_event.wait(timeout=5.0):
                        self.query_result.emit(result[0] if result else {'success': False, 'error': '无响应'})
                    else:
                        self.query_result.emit({'success': False, 'error': '查询超时'})
                except Exception as e:
                    self.query_result.emit({'success': False, 'error': str(e)})
                    
            # 处理写入任务
            if self.write_queue:
                task = self.write_queue.pop(0)
                try:
                    result = []
                    callback_event = threading.Event()
                    
                    def callback(response):
                        result.append(response)
                        callback_event.set()
                        
                    self.db_manager.write(
                        task['db_type'],
                        task['sql'],
                        task['params'],
                        callback=callback
                    )
                    
                    if callback_event.wait(timeout=5.0):
                        self.write_result.emit(result[0] if result else {'success': False, 'error': '无响应'})
                    else:
                        self.write_result.emit({'success': False, 'error': '写入超时'})
                except Exception as e:
                    self.write_result.emit({'success': False, 'error': str(e)})
                    
            time.sleep(0.1)  # 避免CPU占用过高
            
    def stop(self):
        """停止工作线程"""
        self.running = False

class StatusPage(QWidget):
    """状态预览页面"""
    def __init__(self, db_worker):
        super().__init__()
        self.db_worker = db_worker
        self.node_widgets = {}
        self.init_ui()
        self.start_refresh_timer()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("节点状态监控")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 节点状态容器
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.nodes_layout = QGridLayout(scroll_widget)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # 创建节点状态显示
        self.create_node_widgets()
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新状态")
        refresh_btn.clicked.connect(self.refresh_status)
        layout.addWidget(refresh_btn)
        
        self.setLayout(layout)
        
    def create_node_widgets(self):
        """创建节点状态显示组件"""
        # STA节点 (STA01-STA04)
        sta_group = QGroupBox("状态节点 (STA)")
        sta_layout = QGridLayout(sta_group)
        
        for i in range(1, 5):
            node_id = f"STA{i:02d}"
            widget = self.create_single_node_widget(node_id)
            self.node_widgets[node_id] = widget
            sta_layout.addWidget(widget, (i-1)//2, (i-1)%2)
            
        self.nodes_layout.addWidget(sta_group, 0, 0)
        
        # DET节点 (DET01-DET06)
        det_group = QGroupBox("检测节点 (DET)")
        det_layout = QGridLayout(det_group)
        
        for i in range(1, 7):
            node_id = f"DET{i:02d}"
            widget = self.create_single_node_widget(node_id)
            self.node_widgets[node_id] = widget
            det_layout.addWidget(widget, (i-1)//3, (i-1)%3)
            
        self.nodes_layout.addWidget(det_group, 1, 0)
        
    def create_single_node_widget(self, node_id):
        """创建单个节点状态组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 节点ID
        id_label = QLabel(node_id)
        id_label.setFont(QFont("Arial", 12, QFont.Bold))
        id_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(id_label)
        
        # 在线状态
        online_label = QLabel("离线")
        online_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(online_label)
        
        # 激活状态
        active_label = QLabel("未激活")
        active_label.setStyleSheet("color: gray;")
        layout.addWidget(active_label)
        
        # 最后更新时间
        time_label = QLabel("未知")
        time_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(time_label)
        
        # 存储引用
        widget.online_label = online_label
        widget.active_label = active_label
        widget.time_label = time_label
        
        return widget
        
    def update_node_status(self, node_id, status_data):
        """更新节点状态显示"""
        if node_id not in self.node_widgets:
            return
            
        widget = self.node_widgets[node_id]
        if status_data:
            # 在线状态
            online = status_data.get('online', status_data.get('online_status', False))
            if online:
                widget.online_label.setText("在线")
                widget.online_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                widget.online_label.setText("离线")
                widget.online_label.setStyleSheet("color: red; font-weight: bold;")
                
            # 激活状态
            active = status_data.get('active', status_data.get('active_status', 0))
            if active > 0:
                widget.active_label.setText(f"激活: {active}")
                widget.active_label.setStyleSheet("color: blue; font-weight: bold;")
            else:
                widget.active_label.setText("未激活")
                widget.active_label.setStyleSheet("color: gray;")
                
            # 更新时间
            last_update = status_data.get('last_update', '')
            if last_update:
                widget.time_label.setText(f"更新: {last_update}")
            else:
                widget.time_label.setText("未知")
                
    def refresh_status(self):
        """刷新所有节点状态"""
        for node_id in self.node_widgets.keys():
            self.db_worker.add_query(
                DatabaseType.NODE_STATUS,
                "SELECT * FROM node_status WHERE node_id=?",
                (node_id,)
            )
            
    def start_refresh_timer(self):
        """启动自动刷新定时器"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(5000)  # 5秒刷新一次
        
    def handle_query_result(self, result):
        """处理查询结果"""
        if result['success'] and result['data']:
            for node_data in result['data']:
                node_id = node_data.get('node_id')
                if node_id:
                    self.update_node_status(node_id, node_data)

class ConfigPage(QWidget):
    """系统配置页面"""
    def __init__(self, db_worker):
        super().__init__()
        self.db_worker = db_worker
        self.current_config = None
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("游戏配置管理")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 配置信息展示文本框
        info_group = QGroupBox("当前配置信息")
        info_layout = QVBoxLayout(info_group)
        
        self.config_info_text = QTextEdit()
        self.config_info_text.setReadOnly(True)
        self.config_info_text.setMaximumHeight(100)
        self.config_info_text.setFont(QFont("Arial", 10))
        self.config_info_text.setPlainText("正在加载配置信息...")
        info_layout.addWidget(self.config_info_text)
        
        layout.addWidget(info_group)
        
        # 配置表单
        form_group = QGroupBox("修改配置")
        form_layout = QFormLayout(form_group)
        
        # 队伍数量
        self.team_count_combo = QComboBox()
        self.team_count_combo.addItems(["2", "3", "4"])
        form_layout.addRow("队伍数量:", self.team_count_combo)
        
        # 游戏模式
        self.game_mode_combo = QComboBox()
        self.game_mode_combo.addItems(["conquer", "defense", "race"])
        form_layout.addRow("游戏模式:", self.game_mode_combo)
        
        # 游戏状态
        self.game_state_combo = QComboBox()
        self.game_state_combo.addItems(["unstart", "running", "paused", "finished"])
        form_layout.addRow("游戏状态:", self.game_state_combo)
        
        layout.addWidget(form_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        
        refresh_btn = QPushButton("刷新配置")
        refresh_btn.clicked.connect(self.load_config)
        button_layout.addWidget(refresh_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def load_config(self):
        """加载游戏配置"""
        self.db_worker.add_query(
            DatabaseType.GAME_CONFIG,
            "SELECT * FROM game_config ORDER BY id DESC LIMIT 1"
        )
        
    def save_config(self):
        """保存游戏配置"""
        if not self.current_config:
            QMessageBox.warning(self, "警告", "请先加载配置")
            return
            
        config = {
            'team_count': int(self.team_count_combo.currentText()),
            'game_mode': self.game_mode_combo.currentText(),
            'game_state': self.game_state_combo.currentText()
        }
        
        # 显示确认框
        reply = QMessageBox.question(
            self, 
            "确认保存", 
            f"确定要保存以下配置吗？\n\n"
            f"队伍数量: {config['team_count']}队\n"
            f"游戏模式: {self._get_game_mode_name(config['game_mode'])}\n"
            f"游戏状态: {self._get_game_state_name(config['game_state'])}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 更新配置
            self.db_worker.add_write(
                DatabaseType.GAME_CONFIG,
                "UPDATE game_config SET team_count=?, game_mode=?, game_state=? WHERE id=?",
                (config['team_count'], config['game_mode'], config['game_state'], self.current_config['id'])
            )
        
    def _get_game_mode_name(self, mode):
        """获取游戏模式的中文名称"""
        mode_names = {
            'conquer': '征服模式',
            'defense': '防守模式', 
            'race': '竞速模式'
        }
        return mode_names.get(mode, mode)
    
    def _get_game_state_name(self, state):
        """获取游戏状态的中文名称"""
        state_names = {
            'unstart': '未开始',
            'running': '进行中',
            'paused': '已暂停',
            'finished': '已结束'
        }
        return state_names.get(state, state)
        
    def update_config_display(self, config):
        """更新配置显示"""
        if config:
            self.current_config = config
            
            # 更新下拉框
            self.team_count_combo.setCurrentText(str(config.get('team_count', 2)))
            self.game_mode_combo.setCurrentText(config.get('game_mode', 'conquer'))
            self.game_state_combo.setCurrentText(config.get('game_state', 'unstart'))
            
            # 更新配置信息文本框
            info_text = (
                f"配置ID: {config.get('id', '未知')}\n"
                f"队伍数量: {config.get('team_count', 2)}队\n"
                f"游戏模式: {self._get_game_mode_name(config.get('game_mode', 'conquer'))}\n"
                f"游戏状态: {self._get_game_state_name(config.get('game_state', 'unstart'))}\n"
                f"更新时间: {config.get('timestamp', '未知')}"
            )
            self.config_info_text.setPlainText(info_text)
        else:
            self.config_info_text.setPlainText("未找到配置信息")
            
    def handle_query_result(self, result):
        """处理查询结果"""
        logger.debug(f"收到配置查询结果: {result}")
        
        if result.get('success'):
            data = result.get('data', [])
            if data and isinstance(data, list) and len(data) > 0:
                # 获取第一条配置记录
                config_data = data[0]
                logger.debug(f"解析配置数据: {config_data}")
                self.update_config_display(config_data)
            else:
                logger.warning("配置查询成功但数据为空")
                self.update_config_display(None)
        else:
            error_msg = result.get('error', '未知错误')
            logger.error(f"配置查询失败: {error_msg}")
            QMessageBox.warning(self, "警告", f"加载配置失败: {error_msg}")
            self.config_info_text.setPlainText("加载配置失败，请检查数据库连接")
            
    def handle_write_result(self, result):
        """处理写入结果"""
        logger.debug(f"收到配置写入结果: {result}")
        
        if result.get('success'):
            QMessageBox.information(self, "成功", "配置保存成功！\n\n配置已成功更新到数据库。")
            # 延迟一小段时间后重新加载，确保数据库写入完成
            QTimer.singleShot(500, self.load_config)
        else:
            error_msg = result.get('error', '未知错误')
            logger.error(f"配置保存失败: {error_msg}")
            QMessageBox.critical(self, "错误", f"保存配置失败！\n\n错误信息: {error_msg}\n\n请检查数据库连接后重试。")

class LogsPage(QWidget):
    """系统日志页面"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_logs()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("系统日志")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_text)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("刷新日志")
        refresh_btn.clicked.connect(self.load_logs)
        button_layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("清空显示")
        clear_btn.clicked.connect(self.clear_logs)
        button_layout.addWidget(clear_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def load_logs(self):
        """加载日志文件"""
        try:
            log_dir = Path(__file__).parent / "log"
            log_files = list(log_dir.glob("*.log"))
            
            log_content = ""
            for log_file in sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:  # 最近5个文件
                log_content += f"\n=== {log_file.name} ===\n"
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        # 读取最后100行
                        lines = f.readlines()[-100:]
                        log_content += "".join(lines)
                except Exception as e:
                    log_content += f"读取失败: {str(e)}\n"
                    
            self.log_text.setText(log_content)
            self.log_text.moveCursor(self.log_text.textCursor().End)
            
        except Exception as e:
            self.log_text.setText(f"加载日志失败: {str(e)}")
            
    def clear_logs(self):
        """清空日志显示"""
        self.log_text.clear()

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.db_worker = DatabaseWorker(db_manager)
        self.init_ui()
        self.setup_database_connections()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("战鼓系统 - 桌面管理端")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 状态页面
        self.status_page = StatusPage(self.db_worker)
        self.tabs.addTab(self.status_page, "状态预览")
        
        # 配置页面
        self.config_page = ConfigPage(self.db_worker)
        self.tabs.addTab(self.config_page, "系统配置")
        
        # 日志页面
        self.logs_page = LogsPage()
        self.tabs.addTab(self.logs_page, "系统日志")
        
        # 主布局
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.tabs)
        
    def setup_database_connections(self):
        """设置数据库连接"""
        # 连接数据库工作线程的信号
        self.db_worker.query_result.connect(self.handle_query_result)
        self.db_worker.write_result.connect(self.handle_write_result)
        
        # 启动数据库工作线程
        self.db_worker.start()
        
    def handle_query_result(self, result):
        """处理查询结果"""
        current_tab = self.tabs.currentWidget()
        if isinstance(current_tab, StatusPage):
            current_tab.handle_query_result(result)
        elif isinstance(current_tab, ConfigPage):
            current_tab.handle_query_result(result)
            
    def handle_write_result(self, result):
        """处理写入结果"""
        current_tab = self.tabs.currentWidget()
        if isinstance(current_tab, ConfigPage):
            current_tab.handle_write_result(result)
            
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止数据库工作线程
        self.db_worker.stop()
        self.db_worker.wait(3000)  # 等待3秒
        
        # 关闭数据库连接
        if hasattr(self.db_manager, 'stop'):
            self.db_manager.stop()
            
        event.accept()

def main():
    """主函数"""
    # 初始化数据库管理器
    db_manager = DatabaseManager()
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow(db_manager)
    window.show()
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
