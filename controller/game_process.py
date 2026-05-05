import time
import logging
import threading
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
            if status != None:
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
            'volume': 1.0,  # 音量
            'voice': None  # 语音
        }

        # 测试节点状态读取
        self._test_node_status()

    def _init_tts(self):
        """初始化Edge TTS引擎"""
        try:
            import edge_tts
            import urllib.request
            
            # 检查网络连接
            try:
                urllib.request.urlopen('http://www.bing.com', timeout=3)
            except Exception as e:
                logger.error(f"网络连接检查失败: {str(e)}")
                raise Exception("无法连接到互联网，请检查网络连接")
            
            # 尝试不同的语音模型
            test_voices = [
                "zh-CN-YunxiNeural",  # 年轻男声
                "zh-CN-YunyangNeural", # 新闻男声
                "zh-CN-XiaoxiaoNeural" # 年轻女声
            ]
            
            for voice in test_voices:
                try:
                    # 测试语音质量
                    test_text = "欢迎"
                    communicate = edge_tts.Communicate(text=test_text, voice=voice)
                    import asyncio
                    awaitable = communicate.save("test_tts.mp3")
                    asyncio.run(awaitable)
                    
                    self.tts_voice = voice
                    logger.info(f"TTS引擎(EdgeTTS)初始化成功，使用语音: {voice}")
                    return True
                except edge_tts.exceptions.NoAudioReceived:
                    logger.warning(f"语音 {voice} 未返回音频，尝试下一个")
                    continue
                except Exception as e:
                    logger.warning(f"语音 {voice} 测试失败: {str(e)}")
                    continue
            
            raise Exception("所有测试语音均无法获取音频")
        except Exception as e:
            logger.error(f"EdgeTTS初始化失败: {str(e)}")
            raise Exception(f"TTS引擎初始化失败: {str(e)}")

    def _play_tts(self, text):
        """播放TTS语音"""
        if not hasattr(self, 'tts_voice'):
            raise Exception("TTS引擎未初始化")
            
        try:
            import edge_tts
            import asyncio
            import os
            import uuid
            from pathlib import Path
            import subprocess
            
            # 确保临时目录存在
            temp_dir = Path(__file__).parent / "resource" / "tts_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            temp_file = temp_dir / f"tts_{uuid.uuid4().hex}.mp3"
            
            try:
                # 在文本前添加空格，确保语音咬字清晰
                processed_text = f" {text.strip()}"

                # 生成语音文件
                communicate = edge_tts.Communicate(text=processed_text, voice=self.tts_voice)
                asyncio.run(communicate.save(str(temp_file)))
                
                # 播放生成的语音文件
                subprocess.run(["ffplay", "-nodisp", "-autoexit", str(temp_file)])
                
                logger.info(f"TTS播放: {text}")
                self.log_audio(text)
                return True
            finally:
                # 确保删除临时文件
                try:
                    if temp_file.exists():
                        os.unlink(temp_file)
                        logger.debug(f"已删除临时语音文件: {temp_file}")
                except Exception as e:
                    logger.warning(f"删除临时语音文件失败: {str(e)}")
        except Exception as e:
            logger.error(f"TTS播放失败: {str(e)}")
            raise Exception("TTS播放失败")

    def _process_tts_queue(self):
        """保留方法但不实现"""
        logger.warning("_process_tts_queue不应被调用")

    def _get_game_config(self):
        """获取游戏配置"""
        if not hasattr(self, 'db_manager'):
            logger.debug("数据库管理器未初始化")
            return None
            
        self._game_config_result = None
        self._callback_event = threading.Event()
        
        def callback(response):
            logger.debug(f"收到游戏配置回调: {response}")
            if not response['success']:
                logger.error(f"获取游戏配置失败: {response.get('error', '未知错误')}")
            else:
                logger.debug(f"成功获取游戏配置: {response['data']}")
                self._game_config_result = response['data'][0] if response['data'] else None
            self._callback_event.set()
                
        self.db_manager.query(
            DatabaseType.GAME_CONFIG,
            "SELECT * FROM game_config ORDER BY id DESC LIMIT 1",
            callback=callback
        )
        
        # 等待回调完成或超时
        if not self._callback_event.wait(timeout=3.0):
            logger.warning("获取游戏配置超时")
            return None
            
        logger.debug(f"最终获取的游戏配置: {self._game_config_result}")
        return self._game_config_result 

    def _update_game_config(self, config):
        """更新游戏配置"""
        if not hasattr(self, 'db_manager'):
            return False
            
        # 验证必要字段
        if 'game_state' not in config:
            logger.error("更新游戏配置失败: 缺少game_state字段")
            return False
            
        # 尝试获取最新配置ID
        latest_config = self._get_game_config()
        if not latest_config or 'id' not in latest_config:
            logger.error("更新游戏配置失败: 无法获取最新配置ID")
            return False
            
        success = []
        def callback(response):
            if not response['success']:
                logger.error(f"更新游戏配置失败: {response.get('error', '未知错误')}")
            success.append(response['success'])
            
        self.db_manager.write(
            DatabaseType.GAME_CONFIG,
            "UPDATE game_config SET game_state=? WHERE id=?",
            (config['game_state'], latest_config['id']),
            callback=callback
        )
        
        return success[0] if success else False

    def _parse_node_status(self, node_data, node_id):
        """解析节点状态数据"""
        if not node_data:
            logger.warning(f"节点 {node_id} 状态数据为空")
            return None
            
        try:
            # 兼容两种数据格式：
            # 1. 数据库原始格式：{'node_id': ..., 'online_status': ..., 'active_status': ...}
            # 2. 格式化后格式：{'node_id': ..., 'online': ..., 'active': ...}
            return {
                'node_id': str(node_data.get('node_id', node_data.get('node_id', ''))),
                'online_status': bool(node_data.get('online_status', node_data.get('online', False))),
                'active_status': 0 if int(node_data.get('active_status', node_data.get('active', 0))) == 0 else 1,
                'activator': str(node_data.get('activator','')),  
                'last_update': node_data.get('last_update', '')
            }
        except Exception as e:
            logger.error(f"解析节点 {node_id} 状态时发生异常: {str(e)}")
            logger.debug(f"异常数据: {node_data}")
            return None

    def _get_node_status(self, node_id):
        """获取节点状态（线程安全）"""
        if not hasattr(self, 'db_manager') or not isinstance(self.db_manager, DatabaseManager):
            logger.warning("数据库管理器未初始化或无效")
            return None
            
        result = []
        callback_event = threading.Event()
        query_lock = threading.Lock()
        
        def callback(response):
            with query_lock:
                try:
                    if not response or not response.get('success'):
                        error_msg = response.get('error', '未知错误') if response else '无响应'
                        logger.error(f"获取节点状态失败: {error_msg}")
                        return
                        
                    if not response.get('data'):
                        logger.warning(f"节点 {node_id} 状态数据为空")
                        return
                        
                    from pprint import pformat
                    logger.debug(f"完整原始节点数据:\n{pformat(response['data'], indent=2, width=120)}")
                    for node in response['data']:
                        parsed = self._parse_node_status(node, node_id)
                        if parsed and str(parsed['node_id']) == str(node_id):
                            result.append(parsed)
                            break
                finally:
                    callback_event.set()
                    
        try:
            with query_lock:
                self.db_manager.query(
                    DatabaseType.NODE_STATUS,
                    "SELECT * FROM node_status WHERE node_id=?",
                    (node_id,),
                    callback=callback
                )
                
            # 等待回调完成或超时(3秒)
            if not callback_event.wait(timeout=3.0):
                logger.warning(f"获取节点 {node_id} 状态超时")
                return None
                
            return result[0] if result else None
        except Exception as e:
            logger.error(f"查询节点 {node_id} 状态时发生异常: {str(e)}")
            return None

    def _update_node_status(self, node_id, status):
        """更新节点状态"""
        if not hasattr(self, 'db_manager'):
            return False
            
        success = []
        def callback(response):
            if not response['success']:
                logger.error(f"更新节点状态失败: {response.get('error', '未知错误')}")
            success.append(response['success'])
            
        if 'activator' in status:
            self.db_manager.write(
                DatabaseType.NODE_STATUS,
                "UPDATE node_status SET active_status=?, activator=? WHERE node_id=?",
                (status['active_status'], status['activator'], node_id),
                callback=callback
            )
        else:
            self.db_manager.write(
                DatabaseType.NODE_STATUS,
                "UPDATE node_status SET active_status=? WHERE node_id=?",
                (status['active_status'], node_id),
                callback=callback
            )
        
        return success[0] if success else False

    def _monitor_game(self):
        """游戏监控函数"""
        time.sleep(1)
        logger.info("进入游戏监控模式")
        
        while True:
            config = self._get_game_config()
            if not config or config['game_state'] == 'unstart':
                self._play_tts("对局终止")
                return
            
            # 根据游戏模式处理
            if config['game_mode'] == 'conquer':
                self._handle_conquer_mode(config['team_count'])
                return
            elif config['game_mode'] == 'defense':  
                self._handle_defense_mode(config['team_count'])
                return
            elif config['game_mode'] == 'race':  
                self._handle_race_mode(config['team_count'])
                return
            else:
                self._play_tts("尚未开放该模式")
                return


    def _play_local_mp3(self, file_path):
        """播放本地mp3文件"""
        try:
            import subprocess
            from pathlib import Path
            
            # 检查文件是否存在
            mp3_path = Path(__file__).parent / "resource" / "tts_temp" / file_path
            if not mp3_path.exists():
                raise FileNotFoundError(f"MP3文件不存在: {mp3_path}")
                
            # 播放mp3文件
            subprocess.run(["ffplay", "-nodisp", "-autoexit", str(mp3_path)])
            logger.info(f"播放本地MP3: {file_path}")
            return True
        except Exception as e:
            logger.error(f"播放本地MP3失败: {str(e)}")
            raise Exception("播放本地MP3失败")


    class _C4BeepThread(threading.Thread):
        """C4滴滴声播放线程(支持动态间隔)"""
        def __init__(self, game_process, dismantle_time):
            super().__init__(daemon=True)
            self.game_process = game_process
            self.stop_event = threading.Event()
            self.start_time = time.time()
            self.dismantle_time = dismantle_time
            
        def calculate_interval(self):
            """计算当前滴滴声模式"""
            elapsed = time.time() - self.start_time
            # 响一下
            if elapsed < self.dismantle_time/2:
                return "c4-dididi.mp3"
            # 响两下
            elif elapsed > self.dismantle_time / 2 and self.dismantle_time-elapsed > 30: 
                return "c4-dididi2.mp3"
            # 响三下
            else:
                return "c4-dididi3.mp3"
            
        def run(self):
            """主循环"""
            while not self.stop_event.is_set():
                try:
                    self.game_process._play_local_mp3(self.calculate_interval())
                    time.sleep(1)
                except Exception as e:
                    self.game_process.logger.error(f"C4滴滴声线程异常: {str(e)}")
                    break


    def _handle_race_mode(self, team_count):
        """处理C4爆破模式"""
        # A队下包，B队拆包

        # 启动滴滴声线程
        c4_beep_thread = None

        # 游戏配置
        if team_count == 1:
            place_time =3*60 # 3分钟
            dismantle_time = 3*60 # 3分钟
        elif team_count == 2:
            place_time =5*60 # 5分钟
            dismantle_time = 5*60 # 5分钟
        elif team_count == 3:
            place_time =8*60 # 8分钟
            dismantle_time = 8*60 # 8分钟
        c4_condition = False

        self._play_tts("游戏准备开始,5,4,3,2,1,出发")   

        # 重置节点激活状态
        self._update_node_status(f"DET{6:02d}", {'active_status': 0})
                
        start_time = time.time()  # 记录游戏开始时间

        while True:
                # 检查游戏状态
                config = self._get_game_config()
                if not config or config['game_state'] == 'unstart':
                    self._play_tts("对局意外终止")
                    if c4_beep_thread and c4_beep_thread.is_alive():
                        c4_beep_thread.stop_event.set()
                        c4_beep_thread.join()                    
                    return
        
                # 检查是否超时未下包
                elapsed_time = time.time() - start_time
                if not c4_condition and elapsed_time > place_time:
                    
                    self._play_tts("A队超时未放置C4炸药包，B队取得胜利，对局结束")
                
                    # 重置节点激活状态
                    for i in range(1, 5):
                        self._update_node_status(f"STA{i:02d}", {'active_status': 0})
                    self._update_node_status(f"DET{6:02d}", {'active_status': 0})

                    # 重置游戏状态
                    self._update_game_config({
                        'game_state': 'unstart'
                    })
                    return
            
                 # 检查是否超时未拆包
                if  c4_condition and elapsed_time > dismantle_time:

                    # 停止滴滴声线程
                    if c4_beep_thread and c4_beep_thread.is_alive():
                        c4_beep_thread.stop_event.set()
                        c4_beep_thread.join()

                    self._play_local_mp3("c4-boom.mp3")

                    self._play_tts("B队超时未拆除C4炸药包，A队取得胜利，对局结束")
                
                    # 重置节点激活状态
                    for i in range(1, 5):
                        self._update_node_status(f"STA{i:02d}", {'active_status': 0})
                    self._update_node_status(f"DET{6:02d}", {'active_status': 0})

                    # 重置游戏状态
                    self._update_game_config({
                        'game_state': 'unstart'
                    })
                    return

                # 检查C4炸药包状态
                node_id = f"DET{6:02d}"
                node = self._get_node_status(node_id)
            
                # 炸药包被激活
                if node and node['active_status'] == 1 and not c4_condition and node['activator'] == str(1):

                    # 重置节点激活状态
                    self._update_node_status(f"DET{6:02d}", {'active_status': 0})

                    c4_condition = True
                    start_time = time.time()  # 重置计时器为拆包时间
                    self._play_tts("C4炸药包被激活")
                     
                    # 启动滴滴声线程并传入拆包时间
                    c4_beep_thread = self._C4BeepThread(self, dismantle_time)
                    c4_beep_thread.start()

                    node = None  # 重置节点状态变量

                # 炸药包被拆除
                if node and node['active_status'] == 1 and c4_condition and node['activator'] == str(2):
                    # 停止滴滴声线程
                    if c4_beep_thread and c4_beep_thread.is_alive():
                        c4_beep_thread.stop_event.set()
                        c4_beep_thread.join()

                    self._play_tts("C4炸药包被拆除，B队取得胜利，对局结束")

                    # 重置节点激活状态
                    for i in range(1, 5):
                        self._update_node_status(f"STA{i:02d}", {'active_status': 0})
                    self._update_node_status(f"DET{6:02d}", {'active_status': 0})

                    # 重置游戏状态
                    self._update_game_config({
                        'game_state': 'unstart'
                    })
                    return
            
    def _handle_defense_mode(self, team_count):
        """处理占点模式"""
        team_names = ['A队', 'B队', 'C队', '滴队']
        team_scores = [0] * 4  # 用于存储各队得分
        det_previous_data = [0] * 5  # 用于存储上一次的DET状态

        # 提前将未参与的队伍名称设为None
        for i in range(1, 5):
            node = self._get_node_status(f"STA{i:02d}")
            if node and node['active_status'] == 0:
                team_names[i-1] = None

        # 判断点的个数
        if team_names[0] != None and team_names[1] != None :
            points_number = 5
            win_number = 3
            # AB全场
        elif (team_names[1] != None and team_names[3] != None) or (team_names[0] != None and team_names[2] != None):    
            # BD或AC半场        
            points_number = 3
            win_number = 2

        # 重置节点激活状态
        for i in range(1, 6):
            self._update_node_status(f"DET{i:02d}", {'active_status': 0})
        
        self._play_tts("游戏准备开始,5,4,3,2,1,出发")   

        while True:
            # 检查游戏状态
            config = self._get_game_config()
            if not config or config['game_state'] == 'unstart':
                self._play_tts("对局意外终止")

            # 检查各密码盒状态
            for i in range(1, points_number+1):
                node_id = f"DET{i:02d}"
                node = self._get_node_status(node_id)

                if node and node['active_status'] == 1:

                    # i密码盒被摁下
                    for j in range(1, 5):

                        #判断是x队摁下 
                        if team_names[j-1] is not None and node['activator'] == str(j) and det_previous_data[i-1] != j:

                            # 计算得分
                            team_scores[j-1] = team_scores[j-1] + 1

                            if det_previous_data[i-1] != 0:
                                team_scores[det_previous_data[i-1]-1] = team_scores[det_previous_data[i-1]-1] - 1

                            # 记录上次数据
                            eliminated_team =str(team_names[j-1]) if team_names[j-1] is not None else None 
                            det_previous_data[i-1] = int(j)

                            self._play_tts(f"{eliminated_team}占领{i}点")

                            # 判断胜利条件
                            if team_scores[j-1] >= win_number:
                                self._play_tts(f"{eliminated_team}取得胜利，对局结束")
                                
                                # 重置节点激活状态
                                for i in range(1, 5):
                                    self._update_node_status(f"STA{i:02d}", {'active_status': 0})
                                    self._update_node_status(f"DET{i:02d}", {'active_status': 0})
                                self._update_node_status(f"DET{5:02d}", {'active_status': 0})

                                # 重置游戏状态
                                self._update_game_config({
                                    'game_state': 'unstart'
                                })
                                return
                            else:
                                break

                        # 无效操作处理
                        elif  team_names[j-1] is not None and node['activator'] == str(j) and det_previous_data[i-1] == int(j):
                            self._play_tts(f"{team_names[j-1]}重复占领{i}点，无效操作")
                            break
                        
                        elif team_names[j-1] is None and node['activator'] == str(j):
                            self._play_tts(f"{i}点有无效操作，未参与的队伍无法占领点位")
                            break
                    

                    # 重置节点激活状态
                    self._update_node_status(f"DET{i:02d}", {'active_status': 0})

            time.sleep(1)
            
    def _handle_conquer_mode(self, team_count):
        """处理征服模式"""

        team_names = ['A队', 'B队', 'C队', '滴队']
        # 提前将未参与的队伍名称设为None
        for i in range(1, 5):
            node = self._get_node_status(f"STA{i:02d}")
            if node and node['active_status'] == 0:
                team_names[i-1] = None     


        # 重置节点激活状态
        for i in range(1, 5):
            self._update_node_status(f"STA{i:02d}", {'active_status': 0})  

        self._play_tts("游戏准备开始,5,4,3,2,1,出发")  

        start_time = time.time()  # 记录游戏开始时间

        while True:
            # 检查游戏状态
            config = self._get_game_config()
            if not config or config['game_state'] == 'unstart':
                self._play_tts("对局意外终止")
                
            # 检查各队伍状态
            for i in range(1, 5):
                node_id = f"STA{i:02d}"
                node = self._get_node_status(node_id)
                if node and node['active_status'] == 1:
                    eliminated_team = team_names[i-1] if team_names[i-1] is not None else None  
                    if eliminated_team:
                        # 检查是否在10秒保护期内
                        current_time = time.time()
                        if current_time - start_time < 10:
                            # 10秒保护期内，不触发淘汰，只重置节点状态
                            self._update_node_status(f"STA{i:02d}", {'active_status': 0})
                            continue
                        
                        team_names[i-1] = None
                        if team_count==2:
                            self._play_tts(f"{eliminated_team}被淘汰")
                            active_teams = sum(1 for team in team_names if team is not None)
                            winner = [team for team in team_names if team is not None][0] if active_teams == 1 else None
                            if winner:
                                self._play_tts(f"{winner}取得胜利，对局结束")
                        else:                         
                            self._play_tts(f"{eliminated_team}被偷家")
                            self._play_tts(f"对局结束")

                        # 重置节点激活状态
                        for i in range(1, 5):
                            self._update_node_status(f"STA{i:02d}", {'active_status': 0})

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
            # 重置节点激活状态
            for i in range(1, 5):
                self._update_node_status(f"STA{i:02d}", {'active_status': 0})  

            # 尝试初始化TTS，但不强制要求
            tts_initialized = self._init_tts()
            if tts_initialized:
                self._play_tts("主控系统已上线，初始化完成，等待玩家入场")
            else:
                logger.warning("TTS初始化失败，继续运行无语音版本")

            # 主监控循环
            self._play_tts("监控系统上线")
            

            while True:
                # 检查游戏配置
                config = self._get_game_config()
                logger.debug(f"游戏配置: {config}")
                if not config:
                    logger.warning("未获取到游戏配置，等待1秒后重试")
                    time.sleep(1)
                    continue
                
                # 检查STA节点激活状态
                active_nodes = 0
                for i in range(1, 5):  # STA01-STA04
                    node_id = f"STA{i:02d}"
                    node = self._get_node_status(node_id)
                    logger.debug(f"检查节点 {node_id} 状态: {node}")
                    if node and node['active_status'] == 1:
                        logger.debug(f"节点 {node_id} 已激活")
                        self._play_tts(f"{['A队','B队','C队','滴队'][i-1]}已就绪")
                        active_nodes += 1
                
                # 爆破模式特殊处理
                if config['game_mode'] == 'race':
                    real_team_count = 2 
                else:
                    real_team_count = config['team_count']

                # 检查是否满足开始条件
                if (active_nodes >= real_team_count and 
                    config['game_state'] == 'unstart'):
                    # 更新游戏状态
                    self._update_game_config({
                        'game_state': 'started'
                    })
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
