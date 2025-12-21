#!/bin/bash
# MQTT Broker部署脚本
# 端口: 1883
# 主题: node/status

# 检查是否已安装mosquitto
if ! command -v mosquitto &> /dev/null
then
    echo "正在安装mosquitto..."
    sudo apt update
    sudo apt install -y mosquitto mosquitto-clients
else
    echo "mosquitto已安装."
fi

# 创建自定义配置文件
CONFIG_FILE="/etc/mosquitto/conf.d/custom.conf"
echo "创建MQTT broker配置文件..."
sudo tee $CONFIG_FILE > /dev/null <<EOF
# 监听所有网络接口
listener 1883 0.0.0.0
protocol mqtt

# 允许匿名连接
allow_anonymous true

# 日志设置
log_dest file /var/log/mosquitto/mosquitto.log
log_type all
connection_messages true
EOF

# 重启mosquitto服务
echo "启动MQTT broker服务..."
sudo systemctl restart mosquitto

# 检查服务状态
echo "MQTT broker运行状态:"
sudo systemctl status mosquitto --no-pager

echo "MQTT broker已启动:"
echo "- 端口: 1883"
echo "- 主题: node/status"
echo "使用以下命令测试订阅:"
echo "  mosquitto_sub -t 'node/status' -v"
