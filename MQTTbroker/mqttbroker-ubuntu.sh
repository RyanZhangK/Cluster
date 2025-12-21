#!/bin/bash
# Ubuntu MQTT Broker安装脚本
# 配置参数
PORT=1883
TOPIC="node/status"
CONFIG_FILE="/etc/mosquitto/conf.d/custom.conf"
LOG_FILE="/var/log/mosquitto/mosquitto.log"

# 检查root权限
if [ "$(id -u)" -ne 0 ]; then
  echo "请使用root用户或sudo运行此脚本"
  exit 1
fi

# 安装依赖
echo "安装必要依赖..."
apt update && apt install -y curl wget

# 检查并安装mosquitto
if ! command -v mosquitto &> /dev/null; then
  echo "正在安装mosquitto..."
  apt install -y mosquitto mosquitto-clients
else
  echo "mosquitto已安装."
fi

# 创建配置文件目录
mkdir -p /etc/mosquitto/conf.d

# 创建配置文件
echo "创建MQTT broker配置文件..."
cat > $CONFIG_FILE <<EOF
# 监听配置
listener $PORT 0.0.0.0
protocol mqtt

# 安全设置
allow_anonymous true

# 日志设置
log_dest file $LOG_FILE
log_type all
connection_messages true
EOF

# 创建日志目录和文件
mkdir -p /var/log/mosquitto
touch $LOG_FILE
chown mosquitto:mosquitto $LOG_FILE
chmod 644 $LOG_FILE

# 启动服务
echo "启动MQTT broker服务..."
systemctl restart mosquitto
systemctl enable mosquitto

# 验证服务状态
echo "检查服务状态..."
if systemctl is-active --quiet mosquitto; then
  echo "MQTT broker已成功启动"
  echo "- 端口: $PORT"
  echo "- 主题: $TOPIC"
  echo "测试命令:"
  echo "  发布: mosquitto_pub -t '$TOPIC' -m 'test'"
  echo "  订阅: mosquitto_sub -t '$TOPIC' -v"
else
  echo "服务启动失败，查看日志:"
  journalctl -u mosquitto -n 50 --no-pager
  exit 1
fi
