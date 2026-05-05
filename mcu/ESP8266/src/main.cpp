/*
 * ESP8266 MQTT节点控制器
 * 
 * 功能：
 * 1. 通过MQTT协议与服务器通信
 * 2. 定期发送心跳包(HEARTBEAT_INTERVAL)
 * 3. 按键触发发送激活报文
 * 4. LED状态指示
 * 
 * 主要配置：
 * - WIFI_SSID/WIFI_PASSWORD: WiFi连接凭证
 * - MQTT_SERVER/MQTT_PORT: MQTT服务器地址
 * - NODE_ID: 节点唯一标识符
 * - BUTTON_PIN/LED_PIN: 按键和LED引脚
 * 
 * 重要函数：
 * - setup_wifi(): 连接WiFi
 * - reconnect(): 连接MQTT服务器
 * - send_heartbeat(): 发送心跳包
 * - send_activation(): 发送激活报文
 * - blinkLED(): LED闪烁控制
 */

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

/******************** 网络配置 ********************/
#define WIFI_SSID "AL210#AuTHoR"
#define WIFI_PASSWORD "11110000"

/******************** MQTT配置 ********************/
#define MQTT_SERVER "156.238.234.207"        //TODO: 请修改为自己的MQTT服务器地址
#define MQTT_PORT 6000                //TODO: 请修改为自己的MQTT服务器端口
#define MQTT_TOPIC "node/status"
#define MQTT_USER "nodeuser"
#define MQTT_PASSWORD "nodeuserpassword"

/******************** 节点配置 ********************/
#define NODE_ID "STA04"      // 节点识别码
#define BUTTON_PIN D1        // 按键引脚(D1)
#define LED_PIN D4           // 板载LED引脚(D4)
#define HEARTBEAT_INTERVAL 180000  // 心跳间隔(ms)，3分钟=180000ms

/******************** 报文配置 ********************/
#define HEARTBEAT_CODE "H0"  // 心跳报文后缀
#define ACTIVATION_CODE "A2" // 激活报文后缀(B队)

WiFiClient espClient;
PubSubClient client(espClient);
unsigned long last_heartbeat = 0;

// 函数前置声明
void blinkLED(int times = 1, int duration = 100);

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);
  
  // 连接WiFi前快速闪烁LED
  while(true) {
    blinkLED(1, 100);
    if(WiFi.begin(WIFI_SSID, WIFI_PASSWORD) != WL_IDLE_STATUS) break;
    delay(100);
  }

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  // 连接MQTT前慢速闪烁LED
  while (!client.connected()) {
    blinkLED(1, 500);
    Serial.print("Attempting MQTT connection...");
    Serial.print("Connecting to MQTT server ");
    Serial.print(MQTT_SERVER);
    Serial.print(":");
    Serial.println(MQTT_PORT);
    
    if (client.connect(NODE_ID, MQTT_USER, MQTT_PASSWORD)) {
      Serial.println("MQTT connected successfully");
      // 订阅主题
      client.subscribe(MQTT_TOPIC);
      Serial.print("Subscribed to topic: ");
      Serial.println(MQTT_TOPIC);
    } else {
      Serial.print("MQTT connection failed, rc=");
      int state = client.state();
      Serial.print(state);
      // 添加状态码解释
      switch(state) {
        case -4: Serial.println(" (Connection timeout)"); break;
        case -3: Serial.println(" (Connection lost)"); break;
        case -2: Serial.println(" (Connect failed)"); break;
        case -1: Serial.println(" (Disconnected)"); break;
        case 1: Serial.println(" (Bad protocol)"); break;
        case 2: Serial.println(" (Bad client ID)"); break;
        case 3: Serial.println(" (Unavailable)"); break;
        case 4: Serial.println(" (Bad credentials)"); break;
        case 5: Serial.println(" (Unauthorized)"); break;
        default: Serial.println(" (Unknown)"); break;
      }
      Serial.print("WiFi status: ");
      Serial.println(WiFi.status());
      Serial.print("Local IP: ");
      Serial.println(WiFi.localIP());
      Serial.println("Will try again in 5 seconds");
      delay(5000);
    }
  }
}

void send_heartbeat() {
  String message = String(NODE_ID) + HEARTBEAT_CODE;
  client.publish(MQTT_TOPIC, message.c_str());
  Serial.println("Heartbeat sent: " + message);
}

void send_activation() {
  String message = String(NODE_ID) + ACTIVATION_CODE;
  client.publish(MQTT_TOPIC, message.c_str());
  Serial.println("Activation sent: " + message);
}

void blinkLED(int times, int duration) {
  if (times <= 0) return; // 防止times为0或负数
  
  for(int i=0; i<times; i++) {
    digitalWrite(LED_PIN, LOW); // LED亮
    delay(duration);
    digitalWrite(LED_PIN, HIGH); // LED灭
    if(i < times-1) delay(duration);
  }
}

// 添加MQTT回调函数
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  for (unsigned int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();
}

void setup() {
  // 基础硬件测试模式
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW); // LED亮
  delay(1000);
  digitalWrite(LED_PIN, HIGH); // LED灭

  // 增强串口初始化调试
  Serial.begin(115200);
  Serial.println("\n\nStarting hardware test...");
  Serial.println("If you see this message, serial is working");
  Serial.print("LED test: ");
  digitalWrite(LED_PIN, LOW);
  Serial.println("LED should be ON");
  delay(1000);
  digitalWrite(LED_PIN, HIGH);
  Serial.println("LED should be OFF");
  
  // 简单网络测试
  Serial.println("\nStarting WiFi test...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 10000) {
    Serial.print(".");
    delay(500);
  }
  Serial.println();
  
  if(WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi connected, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi connection failed!");
  }
  
  // 初始化LED引脚
  pinMode(LED_PIN, OUTPUT);
  blinkLED(2, 50); // 启动时闪烁2次
  
  Serial.println("串口初始化完成，波特率: 115200");
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.println("按键引脚初始化完成");
  blinkLED(1, 50);
  
  setup_wifi();

  // 检测MQTT服务器端口连通性
  Serial.println("\n开始检测MQTT服务器端口连通性...");
  Serial.print("服务器: ");
  Serial.print(MQTT_SERVER);
  Serial.print(":");
  Serial.println(MQTT_PORT);
  
  WiFiClient testClient;
  if (!testClient.connect(MQTT_SERVER, MQTT_PORT)) {
    Serial.println("端口检测失败，无法连接到MQTT服务器");
    Serial.println("可能原因:");
    Serial.println("1. 服务器未运行");
    Serial.println("2. 防火墙阻止了连接");
    Serial.println("3. 网络配置错误");
    while(true) {
      blinkLED(5, 200); // 快速闪烁表示错误
      delay(1000);
    }
  } else {
    Serial.println("端口检测成功，可以连接到MQTT服务器");
    testClient.stop();
  }

  // 完整初始化MQTT客户端
  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(callback);
  
  // 确保MQTT连接
  if (!client.connected()) {
    reconnect();
  }
  
  Serial.println("WiFi和MQTT初始化完成");
  // 初始心跳
  send_heartbeat();
  last_heartbeat = millis();
  Serial.println("初始心跳已发送");
}

void loop() {
  Serial.println("进入主循环");
  if (!client.connected()) {
    Serial.println("MQTT连接断开，尝试重连...");
    reconnect();
  }
  client.loop();
  Serial.println("MQTT消息处理完成");

  // 心跳检测
  if (millis() - last_heartbeat > HEARTBEAT_INTERVAL) {
    blinkLED(2, 50); // 发送心跳时闪烁2次
    send_heartbeat();
    last_heartbeat = millis();
  }

  // 按键检测
  static unsigned long lastDebounceTime = 0;
  static int lastButtonState = HIGH;
  int buttonState = digitalRead(BUTTON_PIN);
  
  Serial.print("按键原始状态: ");
  Serial.println(buttonState);
  Serial.print("内部上拉状态: ");
  Serial.println(digitalRead(BUTTON_PIN));
  
  // 检测状态变化
  if (buttonState != lastButtonState) {
    lastDebounceTime = millis();
  }
  
  if ((millis() - lastDebounceTime) > 50) {
    // 状态稳定
    if (buttonState == LOW) {
      Serial.println("检测到有效按键按下");
      blinkLED(3, 50); // 按键按下闪烁3次
      send_activation();
      Serial.println("已发送激活报文");
      
      // 等待按键释放
      while(digitalRead(BUTTON_PIN) == LOW) {
        delay(10);
      }
      Serial.println("按键已释放");
      blinkLED(1, 50); // 按键释放闪烁1次
    }
  }
  
  lastButtonState = buttonState;
} 