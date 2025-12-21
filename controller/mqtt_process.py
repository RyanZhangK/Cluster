import paho.mqtt.client as mqtt
import time
import logging
import sys
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta

# 从数据库模块导入类型与节点列表以避免在函数调用时未定义
from database_process import DatabaseType, NODE_IDS

# 使用模块本地日志（带轮转）
from pathlib import Path as _Path
from logging_utils import configure_module_logging
logger = configure_module_logging('mqtt_process', _Path(__file__).parent / 'log')

# MQTT配置
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPICS = [
    "node/status",  # 订阅所有节点的状态信息
]

# 节点心跳超时时间（10分钟）
HEARTBEAT_TIMEOUT = 600  

class NodeTimerManager:
    """管理节点心跳计时器"""
    def __init__(self):
        self.timers = {}
        self.lock = threading.Lock()
        
    def reset_timer(self, node_id):
        """重置指定节点的计时器"""
        with self.lock:
            self.timers[node_id] = datetime.now() + timedelta(seconds=HEARTBEAT_TIMEOUT)
            logger.info(f"重置节点 {node_id} 心跳计时器")
            
    def check_timeouts(self, db_callback):
        """检查所有计时器是否超时"""
        with self.lock:
            now = datetime.now()
            for node_id, expire_time in list(self.timers.items()):
                if now > expire_time:
                    logger.warning(f"节点 {node_id} 心跳超时")
                    # 更新数据库状态
                    db_callback(node_id, False)
                    del self.timers[node_id]

class MQTTProcessor:
    def __init__(self):
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.timer_manager = NodeTimerManager()
        self.db_manager = None  # 将在主程序中初始化
        
        # 确保resource目录存在
        self.data_dir = Path(__file__).parent / "resource"
        self.data_dir.mkdir(exist_ok=True)
        
        # 启动计时器检查线程
        self._start_timer_checker()

    def _start_timer_checker(self):
        """启动计时器检查线程"""
        def checker():
            while True:
                if self.db_manager:
                    self.timer_manager.check_timeouts(self._update_node_status)
                time.sleep(10)
                
        thread = threading.Thread(target=checker, daemon=True)
        thread.start()

    def _update_node_status(self, node_id, online_status, active_status=None):
        """更新节点状态到数据库"""
        start_time = time.time()
        
        if not self.db_manager:
            logger.error("数据库管理器未初始化")
            return
            
        sql = "UPDATE node_status SET online_status = ?"
        params = [online_status]
        
        if active_status is not None:
            sql += ", active_status = ?"
            params.append(active_status)
            
        sql += ", last_update = CURRENT_TIMESTAMP WHERE node_id = ?"
        params.append(node_id)
        
        def callback(response):
            elapsed = round((time.time() - start_time)*1000, 2)
            if not response['success']:
                logger.error(f"更新节点状态失败 (耗时{elapsed}ms): {response.get('error', '未知错误')}")
            else:
                logger.info(f"更新节点 {node_id} 状态成功 (耗时{elapsed}ms)")
                # 发布更新后的状态
                self._publish_node_status(node_id)
        
        logger.debug(f"执行SQL: {sql} 参数: {params}")
        self.db_manager.write(
            DatabaseType.NODE_STATUS,
            sql,
            params,
            callback=callback
        )

    def _publish_node_status(self, node_id):
        """发布节点状态到MQTT"""
        start_time = time.time()
        
        if not self.db_manager:
            logger.warning("数据库管理器未初始化，无法发布状态")
            return
            
        def callback(response):
            elapsed = round((time.time() - start_time)*1000, 2)
            if not response['success']:
                logger.error(f"获取节点状态失败 (耗时{elapsed}ms): {response.get('error', '未知错误')}")
            else:
                if not response['data']:
                    logger.warning(f"未找到节点 {node_id} 的状态记录")
                    return
                    
                node = response['data'][0]
                status = {
                    'node_id': node['node_id'],
                    'online': node['online'],
                    'active': node['active'],
                    'timestamp': node['last_update'],
                    'source': 'db_update'
                }
                
                try:
                    payload = json.dumps(status)
                    result = self.client.publish(
                        f"node/{node_id}/status",
                        payload,
                        qos=1
                    )
                    logger.info(f"发布节点状态成功 (耗时{elapsed}ms) - 消息ID: {result.mid}")
                except Exception as e:
                    logger.error(f"发布MQTT消息失败: {str(e)}")
                
        logger.debug(f"查询节点 {node_id} 状态")
        self.db_manager.query(
            DatabaseType.NODE_STATUS,
            "SELECT * FROM node_status WHERE node_id=?",
            (node_id,),
            callback=callback
        )

    def _parse_message(self, raw_msg):
        """解析MQTT消息"""
        try:
            logger.debug(f"原始报文: {raw_msg} (长度: {len(raw_msg)})")
            
            if len(raw_msg) != 7:
                raise ValueError(f"无效消息长度: {len(raw_msg)}")
                
            node_id = raw_msg[:5]
            action_type = raw_msg[5].upper()
            extra_info = raw_msg[6]
            
            logger.debug(f"解析结果 - 节点ID: {node_id}, 类型: {action_type}, 信息: {extra_info}")
            
            if node_id not in NODE_IDS:
                raise ValueError(f"无效节点ID: {node_id}")
                
            if action_type not in ('H', 'A'):
                raise ValueError(f"无效动作类型: {action_type}")
                
            if action_type == 'H' and extra_info != '0':
                raise ValueError("心跳包补充信息必须为0")
                
            if action_type == 'A' and extra_info not in ('1', '2', '3', '4'):
                raise ValueError("激活包补充信息必须为1-4")
                
            return node_id, action_type, extra_info
            
        except Exception as e:
            logger.error(f"报文解析失败: {str(e)}")
            raise

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT连接回调"""
        logger.debug(f"连接回调参数 - rc: {rc}, flags: {flags}, properties: {properties}")
        if rc == 0:
            logger.info("成功连接到MQTT broker")
            # 订阅所有主题
            for topic in MQTT_TOPICS:
                result, mid = client.subscribe(topic)
                logger.debug(f"订阅结果 - topic: {topic}, result: {result}, mid: {mid}")
                logger.info(f"已订阅主题: {topic}")
            logger.debug("连接和订阅完成")
        else:
            logger.error(f"连接MQTT broker失败，错误码: {rc}")

    def on_message(self, client, userdata, msg):
        """MQTT消息回调"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # 解析消息
            node_id, action_type, extra_info = self._parse_message(payload)
            logger.info(f"收到消息 [节点: {node_id}, 类型: {action_type}, 信息: {extra_info}]")
            
            # 处理消息
            if action_type == 'H':
                # 心跳包：更新在线状态并重置计时器
                self._update_node_status(node_id, True)
                self.timer_manager.reset_timer(node_id)
            elif action_type == 'A':
                # 激活包：更新激活状态
                self._update_node_status(node_id, True, int(extra_info))
                
            # 记录原始消息
            with open(self.data_dir / "mqtt_data.log", "a") as f:
                f.write(f"{time.time()},{topic},{payload}\n")
                
        except Exception as e:
            logger.error(f"处理MQTT消息时出错: {str(e)}")

    def run(self):
        """主运行循环"""
        logger.info("MQTT处理模块启动")
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("接收到中断信号，停止MQTT模块")
            self.client.disconnect()
        except Exception as e:
            logger.error(f"MQTT模块运行异常: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        # 初始化数据库管理器
        from database_process import DatabaseManager, DatabaseType, NODE_IDS
        db_manager = DatabaseManager()
        
        # 初始化MQTT处理器
        processor = MQTTProcessor()
        processor.db_manager = db_manager
        
        # 启动模块
        logger.info("MQTT处理模块启动")
        processor.run()
    except Exception as e:
        logger.error(f"MQTT处理模块初始化失败: {str(e)}")
        sys.exit(1)
