#!/bin/bash
# MQTT Broker生产环境部署脚本(Arch Linux版)
# 版本: 1.0
# 端口: 1883
# 主题: node/status

# 检查root权限
if [ "$(id -u)" -ne 0 ]; then
  echo "请使用root用户运行此脚本"
  exit 1
fi

# 安装依赖和mosquitto
echo "安装必要依赖..."
pacman -Sy --noconfirm mosquitto

# 创建生产环境配置文件
CONFIG_FILE="/etc/mosquitto/conf.d/production.conf"
mkdir -p /etc/mosquitto/conf.d
echo "创建生产环境MQTT broker配置文件..."

cat > $CONFIG_FILE <<EOF
# 监听端口和IP
listener 1883 0.0.0.0
protocol mqtt

# 安全设置
allow_anonymous false
password_file /etc/mosquitto/passwd
acl_file /etc/mosquitto/acl

# 日志设置
log_dest file /var/log/mosquitto/mosquitto.log
log_type all
connection_messages true
log_timestamp true

# 资源限制
max_connections 1000
max_queued_messages 1000
message_size_limit 0
persistence true
persistence_location /var/lib/mosquitto/

# 主题设置
# 默认主题: node/status
EOF

# 创建用户密码文件
echo "创建MQTT用户..."
touch /etc/mosquitto/passwd
mosquitto_passwd -b /etc/mosquitto/passwd mqttadmin securepassword123

# 创建ACL访问控制
echo "设置ACL访问控制..."
cat > /etc/mosquitto/acl <<EOF
# 管理员权限
user mqttadmin
topic readwrite #

# 节点权限
user nodeuser
topic write node/status
topic read node/command
EOF

# 设置日志轮转
echo "配置日志轮转..."
cat > /etc/logrotate.d/mosquitto <<EOF
/var/log/mosquitto/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 640 mosquitto mosquitto
    sharedscripts
    postrotate
        systemctl reload mosquitto > /dev/null 2>&1 || true
    endscript
}
EOF

# 设置防火墙规则
echo "配置防火墙..."
if command -v ufw &> /dev/null; then
    ufw allow 1883/tcp
    ufw reload
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=1883/tcp
    firewall-cmd --reload
else
    echo "未检测到ufw或firewalld，请手动配置防火墙"
fi

# 启动服务
echo "启动MQTT broker服务..."
systemctl enable --now mosquitto
systemctl restart mosquitto

# 检查服务状态
echo "MQTT broker运行状态:"
systemctl status mosquitto --no-pager

echo "生产环境MQTT broker部署完成(Arch Linux版):"
echo "- 端口: 1883"
echo "- 默认主题: node/status"
echo "- 管理员用户名: mqttadmin"
echo "- 节点用户名: nodeuser"
echo "使用以下命令测试订阅:"
echo "  mosquitto_sub -h localhost -t 'node/status' -u mqttadmin -P securepassword123 -v"
