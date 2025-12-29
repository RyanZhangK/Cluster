import sys
import time
import threading
from datetime import datetime
from pathlib import Path
import logging
from logging_utils import configure_module_logging

# PySide6 imports
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QComboBox, 
                               QFormLayout, QGroupBox, QTextEdit, QGridLayout, 
                               QMessageBox, QScrollArea, QSplitter, QTabWidget)
from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtGui import QFont, QPalette, QColor, QTextCursor

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

class DatabaseInfoPanel(QWidget):
    """数据库信息浏览面板"""
    def __init__(self, db_worker):
        super().__init__()
        self.db_worker = db_worker
        self.init_ui()
        self.start_refresh_timer()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("数据库信息浏览")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 创建标签页容器
        self.tabs = QTabWidget()
        
        # 节点状态标签页
        self.node_status_tab = self.create_node_status_tab()
        self.tabs.addTab(self.node_status_tab, "节点状态")
        
        # 游戏配置标签页
        self.game_config_tab = self.create_game_config_tab()
        self.tabs.addTab(self.game_config_tab, "游戏配置")
        
        # 系统日志标签页
        self.logs_tab = self.create_logs_tab()
        self.tabs.addTab(self.logs_tab, "系统日志")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
        
    def create_node_status_tab(self):
        """创建节点状态标签页"""
        # 主容器
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # 节点状态容器
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.nodes_layout = QGridLayout(scroll_widget)  # 改为实例变量
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        
        # 创建节点状态显示
        self.node_widgets = {}
        
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
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新节点状态")
        refresh_btn.clicked.connect(self.refresh_node_status)
        main_layout.addWidget(refresh_btn)
        
        return main_widget
        
    def create_single_node_widget(self, node_id):
        """创建单个节点状态组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 节点ID
        id_label = QLabel(node_id)
        id_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        
        # 存储引用到字典中
        widget.setProperty("labels", {
            "online": online_label,
            "active": active_label,
            "time": time_label
        })
        
        return widget
        
    def create_game_config_tab(self):
        """创建游戏配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 配置信息展示文本框
        info_group = QGroupBox("当前配置信息")
        info_layout = QVBoxLayout(info_group)
        
        self.config_info_text = QTextEdit()
        self.config_info_text.setReadOnly(True)
        self.config_info_text.setMaximumHeight(150)
        self.config_info_text.setFont(QFont("Arial", 10))
        self.config_info_text.setPlainText("正在加载配置信息...")
        info_layout.addWidget(self.config_info_text)
        
        layout.addWidget(info_group)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新配置信息")
        refresh_btn.clicked.connect(self.refresh_game_config)
        layout.addWidget(refresh_btn)
        
        return widget
        
    def create_logs_tab(self):
        """创建系统日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
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
        
        return widget
        
    def refresh_node_status(self):
        """刷新所有节点状态"""
        for node_id in self.node_widgets.keys():
            self.db_worker.add_query(
                DatabaseType.NODE_STATUS,
                "SELECT * FROM node_status WHERE node_id=?",
                (node_id,)
            )
            
    def refresh_game_config(self):
        """刷新游戏配置"""
        self.db_worker.add_query(
            DatabaseType.GAME_CONFIG,
            "SELECT * FROM game_config ORDER BY id DESC LIMIT 1"
        )
        
    def load_logs(self):
        """加载日志文件"""
        try:
            log_dir = Path(__file__).parent / "log"
            logger.debug(f"尝试从目录加载日志: {log_dir}")
            
            if not log_dir.exists():
                error_msg = f"日志目录不存在: {log_dir}"
                logger.error(error_msg)
                self.log_text.setText(f"错误: {error_msg}")
                return
                
            log_files = list(log_dir.glob("*.log"))
            logger.debug(f"找到 {len(log_files)} 个日志文件: {[f.name for f in log_files]}")
            
            if not log_files:
                self.log_text.setText("未找到日志文件")
                return
                
            log_content = f"日志目录: {log_dir}\n"
            log_content += f"找到 {len(log_files)} 个日志文件\n\n"
            
            for log_file in sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:  # 最近5个文件
                log_content += f"\n=== {log_file.name} (最后修改: {datetime.fromtimestamp(log_file.stat().st_mtime)}) ===\n"
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        # 读取最后100行
                        lines = f.readlines()[-100:]
                        if lines:
                            log_content += "".join(lines)
                        else:
                            log_content += "文件为空\n"
                    logger.debug(f"成功读取文件: {log_file.name}, 行数: {len(lines)}")
                except Exception as e:
                    error_msg = f"读取 {log_file.name} 失败: {str(e)}"
                    log_content += error_msg + "\n"
                    logger.error(error_msg)
                    
            self.log_text.setText(log_content)
            self.log_text.moveCursor(QTextCursor.MoveOperation.End)
            logger.debug("日志加载完成")
            
        except Exception as e:
            error_msg = f"加载日志失败: {str(e)}"
            logger.error(error_msg)
            self.log_text.setText(f"错误: {error_msg}")
            
    def clear_logs(self):
        """清空日志显示"""
        self.log_text.clear()
        
    def update_node_status(self, node_id, status_data):
        """更新节点状态显示"""
        if node_id not in self.node_widgets:
            return
            
        widget = self.node_widgets[node_id]
        labels = widget.property("labels")
        if not labels:
            return
            
        if status_data:
            # 在线状态
            online = status_data.get('online', status_data.get('online_status', False))
            if online:
                labels["online"].setText("在线")
                labels["online"].setStyleSheet("color: green; font-weight: bold;")
            else:
                labels["online"].setText("离线")
                labels["online"].setStyleSheet("color: red; font-weight: bold;")
                
            # 激活状态
            active = status_data.get('active', status_data.get('active_status', 0))
            if active > 0:
                labels["active"].setText(f"激活: {active}")
                labels["active"].setStyleSheet("color: blue; font-weight: bold;")
            else:
                labels["active"].setText("未激活")
                labels["active"].setStyleSheet("color: gray;")
                
            # 更新时间
            last_update = status_data.get('last_update', '')
            if last_update:
                labels["time"].setText(f"更新: {last_update}")
            else:
                labels["time"].setText("未知")
                
    def update_game_config(self, config_data):
        """更新游戏配置显示"""
        if config_data:
            info_text = (
                f"配置ID: {config_data.get('id', '未知')}\n"
                f"队伍数量: {config_data.get('team_count', 2)}队\n"
                f"游戏模式: {self._get_game_mode_name(config_data.get('game_mode', 'conquer'))}\n"
                f"游戏状态: {self._get_game_state_name(config_data.get('game_state', 'unstart'))}\n"
                f"更新时间: {config_data.get('timestamp', '未知')}"
            )
            self.config_info_text.setPlainText(info_text)
        else:
            self.config_info_text.setPlainText("未找到配置信息")
            
    def _get_game_mode_name(self, mode):
        """获取游戏模式的中文名称"""
        mode_names = {
            'conquer': '征服模式',
            'defense': '夺点模式', 
            'race': '爆破模式'
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
        
    def start_refresh_timer(self):
        """启动自动刷新定时器"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_refresh)
        self.timer.start(5000)  # 5秒刷新一次
        
    def auto_refresh(self):
        """自动刷新"""
        current_tab = self.tabs.currentWidget()
        if current_tab == self.node_status_tab:
            self.refresh_node_status()
        elif current_tab == self.game_config_tab:
            self.refresh_game_config()
        elif current_tab == self.logs_tab:
            self.load_logs()

class ConfigEditorPanel(QWidget):
    """配置编辑面板"""
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
        title = QLabel("游戏配置编辑")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
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
        
        # 状态信息
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: green;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
    def load_config(self):
        """加载游戏配置"""
        self.db_worker.add_query(
            DatabaseType.GAME_CONFIG,
            "SELECT * FROM game_config ORDER BY id DESC LIMIT 1"
        )
        self.status_label.setText("正在加载配置...")
        self.status_label.setStyleSheet("color: blue;")
        
    def save_config(self):
        """保存游戏配置"""
        if not self.current_config:
            QMessageBox.warning(self, "警告", "请先加载配置")
            return
            
        config = {
            'team_count': int(self.team_count_combo.currentText()),
            'game_mode': self.game_mode_combo.currentText(),
            'game_state': self.current_config.get('game_state', 'unstart')
        }
        
        # 显示确认框
        reply = QMessageBox.question(
            self, 
            "确认保存", 
            f"确定要保存以下配置吗？\n\n"
            f"队伍数量: {config['team_count']}队\n"
            f"游戏模式: {self._get_game_mode_name(config['game_mode'])}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText("正在保存配置...")
            self.status_label.setStyleSheet("color: blue;")
            
            # 更新配置
            self.db_worker.add_write(
                DatabaseType.GAME_CONFIG,
                "UPDATE game_config SET team_count=?, game_mode=? WHERE id=?",
                (config['team_count'], config['game_mode'], self.current_config['id'])
            )
        
    def update_config(self, config):
        """更新配置显示"""
        if config:
            self.current_config = config
            
            # 只有当配置确实发生变化时才更新下拉框，避免覆盖用户选择
            current_team_count = self.team_count_combo.currentText()
            current_game_mode = self.game_mode_combo.currentText()
            
            config_team_count = str(config.get('team_count', 2))
            config_game_mode = config.get('game_mode', 'conquer')
            
            # 只有当数据库中的值与当前显示值不同时才更新
            if current_team_count != config_team_count:
                self.team_count_combo.setCurrentText(config_team_count)
            
            if current_game_mode != config_game_mode:
                self.game_mode_combo.setCurrentText(config_game_mode)
            
            self.status_label.setText("配置加载完成")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("配置加载失败")
            self.status_label.setStyleSheet("color: red;")
            
    def _get_game_mode_name(self, mode):
        """获取游戏模式的中文名称"""
        mode_names = {
            'conquer': '征服模式',
            'defense': '夺点模式', 
            'race': '爆破模式'
        }
        return mode_names.get(mode, mode)

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
        self.setGeometry(100, 100, 1200, 700)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：数据库信息面板
        self.info_panel = DatabaseInfoPanel(self.db_worker)
        splitter.addWidget(self.info_panel)
        
        # 右侧：配置编辑面板
        self.editor_panel = ConfigEditorPanel(self.db_worker)
        splitter.addWidget(self.editor_panel)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 2)  # 左侧占2/3
        splitter.setStretchFactor(1, 1)  # 右侧占1/3
        
        # 主布局
        layout = QVBoxLayout(central_widget)
        layout.addWidget(splitter)
        
    def setup_database_connections(self):
        """设置数据库连接"""
        # 连接数据库工作线程的信号
        self.db_worker.query_result.connect(self.handle_query_result)
        self.db_worker.write_result.connect(self.handle_write_result)
        
        # 启动数据库工作线程
        self.db_worker.start()
        
    def handle_query_result(self, result):
        """处理查询结果"""
        logger.debug(f"收到查询结果: {result}")
        
        if result.get('success'):
            data = result.get('data', [])
            
            # 判断查询类型并分发处理
            if result.get('timestamp'):  # 这是数据库查询结果
                if data and isinstance(data, list):
                    if len(data) > 0:
                        # 根据数据结构判断类型
                        first_item = data[0]
                        if 'node_id' in first_item:
                            # 节点状态数据
                            for node_data in data:
                                node_id = node_data.get('node_id')
                                if node_id:
                                    self.info_panel.update_node_status(node_id, node_data)
                        elif 'team_count' in first_item:
                            # 游戏配置数据
                            config_data = data[0]
                            self.info_panel.update_game_config(config_data)
                            self.editor_panel.update_config(config_data)
        else:
            error_msg = result.get('error', '未知错误')
            logger.error(f"查询失败: {error_msg}")
            QMessageBox.warning(self, "警告", f"数据库查询失败: {error_msg}")
            
    def handle_write_result(self, result):
        """处理写入结果"""
        logger.debug(f"收到写入结果: {result}")
        
        if result.get('success'):
            QMessageBox.information(self, "成功", "配置保存成功！")
            self.editor_panel.status_label.setText("保存成功")
            self.editor_panel.status_label.setStyleSheet("color: green;")
            # 延迟一小段时间后重新加载，确保数据库写入完成
            QTimer.singleShot(500, self.editor_panel.load_config)
        else:
            error_msg = result.get('error', '未知错误')
            logger.error(f"写入失败: {error_msg}")
            QMessageBox.critical(self, "错误", f"保存配置失败！\n\n错误信息: {error_msg}")
            self.editor_panel.status_label.setText("保存失败")
            self.editor_panel.status_label.setStyleSheet("color: red;")
            
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
