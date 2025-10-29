import time
import logging
import sys
import sqlite3
from pathlib import Path

from pathlib import Path as _Path
from logging_utils import configure_module_logging
from database_process import DatabaseManager, DatabaseType

# 使用模块本地日志（带轮转）
logger = configure_module_logging('game_process', _Path(__file__).parent / 'log')

class GameManager:
    def _init_db(self):
        """初始化游戏数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()
            
            # 创建游戏状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state TEXT,
                    score INTEGER,
                    level INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建音频记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audio_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            logger.info("游戏数据库初始化完成")
        except Exception as e:
            logger.error(f"游戏数据库初始化失败: {str(e)}")
            raise

    def log_audio(self, text):
        """记录音频日志到数据库"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO audio_logs (text) VALUES (?)",
                (text,)
            )
            self.conn.commit()
            logger.info(f"音频日志记录: {text}")
        except Exception as e:
            logger.error(f"记录音频日志失败: {str(e)}")

    def save_game_state(self, state, score, level):
        """保存游戏状态到数据库"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO game_state (state, score, level) VALUES (?, ?, ?)",
                (state, score, level)
            )
            self.conn.commit()
            logger.info(f"保存游戏状态: state={state}, score={score}, level={level}")
        except Exception as e:
            logger.error(f"保存游戏状态失败: {str(e)}")

    def _test_node_status(self):
        """测试读取节点状态"""
        logger.info("开始测试节点状态读取...")
        test_nodes = ['STA01', 'STA02', 'STA03', 'STA04']
        for node_id in test_nodes:
            status = self._get_node_status(node_id)
            if status:
                logger.info(f"节点 {node_id} 状态: 在线={status['online_status']}, 激活={status['active_status']}")
            else:
                logger.warning(f"未找到节点 {node_id} 的状态记录")

    def __init__(self):
        # 数据库连接
        self.db_path = Path(__file__).parent / "resource" / "game_data.db"
        self._init_db()
        
        # 初始化数据库管理器
        self.db_manager = DatabaseManager()
        
        # TTS配置
        self.tts_engine = None
        self.tts_queue = []
        self.tts_config = {
            'rate': 150,  # 语速
            'volume': 0.9,  # 音量
            'voice': None  # 语音
        }

        # 测试节点状态读取
        self._test_node_status()

    def _init_tts(self):
        """初始化TTS引擎"""
        import shutil
        try:
            from gtts import gTTS
            import tempfile
            self.tts_engine = gTTS
            self.tts_temp_dir = tempfile.mkdtemp()
            # 自动检测可用播放命令
            for cmd in ("mpg123", "mpv", "ffplay", "afplay"):
                if shutil.which(cmd):
                    self.play_command = cmd
                    break
            else:
                self.play_command = None
            logger.info("TTS引擎(gTTS)初始化完成, player=%s", self.play_command)
            return True
        except Exception as e:
            logger.error("TTS引擎初始化失败: %s", e)
            # 明确重置属性，避免后续调用 NoneType 出错
            self.tts_engine = None
            self.tts_temp_dir = None
            self.play_command = None
            return False

    def _play_tts(self, text):
        """播放TTS语音"""
        if not hasattr(self, 'tts_engine'):
            logger.error("TTS引擎未初始化")
            return False
            
        try:
            # 添加到语音队列
            self.tts_queue.append(text)
            
            # 如果队列中只有当前语音，立即播放
            if len(self.tts_queue) == 1:
                self._process_tts_queue()
            
            logger.info(f"TTS播放: {text}")
            self.log_audio(text)
            return True
        except Exception as e:
            logger.error(f"TTS播放失败: {str(e)}")
            return False

    def _process_tts_queue(self):
        """处理语音队列"""
        if not self.tts_queue:
            return
            
        text = self.tts_queue[0]
        try:
            import os
            
            # 生成语音文件
            tts = self.tts_engine(text=text, lang='zh-cn')
            temp_file = os.path.join(self.tts_temp_dir, f"tts_{hash(text)}.mp3")
            tts.save(temp_file)
            
            # 使用系统命令播放
            import subprocess
            subprocess.run([self.play_command, temp_file], check=True)
            
            # 删除临时文件
            os.remove(temp_file)
        except Exception as e:
            logger.error(f"TTS播放失败: {str(e)}")
        finally:
            # 移除已播放的语音
            self.tts_queue.pop(0)
            
            # 播放队列中的下一条语音
            if self.tts_queue:
                self._process_tts_queue()

    def _get_game_config(self):
        """获取游戏配置"""
        if not hasattr(self, 'db_manager'):
            return None
            
        result = []
        def callback(response):
            if not response['success']:
                logger.error(f"获取游戏配置失败: {response.get('error', '未知错误')}")
            else:
                result.append(response['data'])
                
        self.db_manager.query(
            DatabaseType.GAME_CONFIG,
            "SELECT * FROM game_config ORDER BY id DESC LIMIT 1",
            callback=callback
        )
        
        return result[0] if result else None

    def _update_game_config(self, config):
        """更新游戏配置"""
        if not hasattr(self, 'db_manager'):
            return False
            
        success = []
        def callback(response):
            if not response['success']:
                logger.error(f"更新游戏配置失败: {response.get('error', '未知错误')}")
            success.append(response['success'])
            
        self.db_manager.write(
            DatabaseType.GAME_CONFIG,
            "UPDATE game_config SET game_state=? WHERE id=?",
            (config['game_state'], config['id']),
            callback=callback
        )
        
        return success[0] if success else False

    def _get_node_status(self, node_id):
        """获取节点状态"""
        if not hasattr(self, 'db_manager'):
            logger.warning("数据库管理器未初始化")
            return None
            
        result = []
        def callback(response):
            if not response['success']:
                logger.error(f"获取节点状态失败: {response.get('error', '未知错误')}")
                logger.debug(f"失败响应详情: {response}")
            else:
                logger.debug(f"数据库返回数据: {response['data']}")
                for node in response['data']:
                    if str(node.get('node_id')) == str(node_id):
                        status = {
                            'node_id': str(node.get('node_id')),
                            'online_status': bool(node.get('online_status', False)),
                            'active_status': int(node.get('active_status', 0)),
                            'last_update': node.get('last_update')
                        }
                        result.append(status)
                        logger.debug(f"成功解析节点状态: {status}")
                        break
                else:
                    logger.warning(f"未找到节点 {node_id} 的状态记录")
                
        self.db_manager.query(
            DatabaseType.NODE_STATUS,
            "SELECT * FROM node_status WHERE node_id=?",
            (node_id,),
            callback=callback
        )
        
        return result[0] if result else None

    def _update_node_status(self, node_id, status):
        """更新节点状态"""
        if not hasattr(self, 'db_manager'):
            return False
            
        success = []
        def callback(response):
            if not response['success']:
                logger.error(f"更新节点状态失败: {response.get('error', '未知错误')}")
            success.append(response['success'])
            
        self.db_manager.write(
            DatabaseType.NODE_STATUS,
            "UPDATE node_status SET active_status=? WHERE node_id=?",
            (status['active_status'], node_id),
            callback=callback
        )
        
        return success[0] if success else False

    def _monitor_game(self):
        """游戏监控函数"""
        logger.info("进入游戏监控模式")
        
        while True:
            config = self._get_game_config()
            if not config or config['game_state'] != 'started':
                self._play_tts("对局终止")
                return
            
            # 根据游戏模式处理
            if config['game_mode'] == 'conquer':
                self._handle_conquer_mode(config['team_count'])
            else:
                self._play_tts("尚未开放该模式")
                return

    def _handle_conquer_mode(self, team_count):
        """处理征服模式"""
        active_teams = team_count
        team_names = ['A队', 'B队', 'C队', 'D队'][:team_count]
        
        while True:
            # 检查游戏状态
            config = self._get_game_config()
            if not config or config['game_state'] != 'started':
                return
            
            # 检查各队伍状态
            for i in range(1, team_count + 1):
                node_id = f"STA{i:02d}"
                node = self._get_node_status(node_id)
                if node and node['active_status'] == 1:
                    self._play_tts(f"{team_names[i-1]}被淘汰")
                    active_teams -= 1
                    # 更新节点状态为未激活
                    self._update_node_status(node_id, {'active_status': 0})
            
            # 检查胜利条件
            if active_teams <= 1:
                winner = None
                for i in range(1, team_count + 1):
                    node_id = f"STA{i:02d}"
                    node = self._get_node_status(node_id)
                    if node and node['active_status'] == 0:
                        winner = team_names[i-1]
                        break
                
                if winner:
                    self._play_tts(f"{winner}取得胜利，对局结束")
                
                # 重置游戏状态
                self._update_game_config({
                    'game_state': 'unstart'
                })
                return
            
            time.sleep(1)

    def run(self):
        """主运行循环"""
        logger.info("游戏模块启动")
        try:
            # 初始化TTS
            if not self._init_tts():
                raise Exception("TTS初始化失败")
            
            # 播放系统上线语音
            self._play_tts("主控系统已上线，初始化完成，等待玩家入场")
            
            # 主监控循环
            while True:
                # 检查游戏配置
                config = self._get_game_config()
                if not config:
                    time.sleep(1)
                    continue
                
                # 检查STA节点激活状态
                active_nodes = 0
                for i in range(1, 5):  # STA01-STA04
                    node_id = f"STA{i:02d}"
                    node = self._get_node_status(node_id)
                    if node and node['active_status'] == 1:
                        self._play_tts(f"{['A队','B队','C队','D队'][i-1]}已就绪")
                        active_nodes += 1
                
                # 检查是否满足开始条件
                if (active_nodes >= config['team_count'] and 
                    config['game_state'] == 'unstart'):
                    # 更新游戏状态
                    self._update_game_config({
                        'game_state': 'started'
                    })
                    # 重置节点激活状态
                    for i in range(1, 5):
                        self._update_node_status(f"STA{i:02d}", {'active_status': 0})
                    
                    # 进入游戏监控
                    self._monitor_game()
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("接收到中断信号，停止游戏模块")
            self._play_tts("系统关闭")
        except Exception as e:
            logger.error(f"游戏模块运行异常: {str(e)}")
            sys.exit(1)
        finally:
            if hasattr(self, 'conn'):
                self.conn.close()

if __name__ == "__main__":
    try:
        game = GameManager()
        game.run()
    except Exception as e:
        logger.error(f"游戏模块初始化失败: {str(e)}")
        sys.exit(1)
