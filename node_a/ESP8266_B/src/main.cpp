#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Ticker.h>

#include <Keypad.h>

/******************** 键盘配置 ********************/
const byte ROWS = 4;
const byte COLS = 4;
char keys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[ROWS] = {D1, D2, D3, D4}; // 行引脚(输出)
byte colPins[COLS] = {D5, D6, D7, D8}; // 列引脚(输入，内部上拉)

// 初始化Keypad实例
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

/******************** 网络配置 ********************/
#define WIFI_SSID "ZG1"
#define WIFI_PASSWORD "ZG888888"

/******************** MQTT配置 ********************/
#define MQTT_SERVER "hk-1.lcf.im"
#define MQTT_PORT 44376
#define MQTT_TOPIC "node/status"
#define MQTT_USER "nodeuser"
#define MQTT_PASSWORD "nodeuserpassword"

/******************** 节点配置 ********************/
#define NODE_ID "DET01"      // 节点识别码
#define HEARTBEAT_INTERVAL 180000  // 心跳间隔(ms)，3分钟=180000ms

/******************** 报文配置 ********************/
#define HEARTBEAT_CODE "H0"  // 心跳报文后缀
#define ACTIVATION_CODE "7355608" // 激活验证码

// 全局变量
WiFiClient espClient;
PubSubClient client(espClient);
Ticker watchdogTicker;
unsigned long lastHeartbeat = 0;
String inputBuffer;
bool isRecording = false;

/**
 * 初始化WiFi连接
 * 自动重试直到连接成功
 * 失败时会自动重启设备
 */
void setupWiFi() {
  Serial.println("\n[网络] 正在连接WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  unsigned long startTime = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    
    // 30秒连接超时自动重启
    if (millis() - startTime > 30000) {
      Serial.println("\n[错误] WiFi连接超时，即将重启...");
      ESP.restart();
    }
  }
  
  Serial.println("\n[网络] WiFi已连接");
  Serial.print("[网络] IP地址: ");
  Serial.println(WiFi.localIP());
}

// 看门狗喂食
void feedWatchdog() {
  ESP.wdtFeed();
}

/**
 * 连接MQTT服务器
 * 包含错误状态码输出和自动重试机制
 */
void connectMQTT() {
  if (!client.connected()) {
    Serial.println("[网络] 尝试连接MQTT服务器...");
    
    // 带状态码的详细错误输出
    if (client.connect(NODE_ID, MQTT_USER, MQTT_PASSWORD)) {
      client.subscribe(MQTT_TOPIC);
      Serial.println("[网络] MQTT已连接");
    } else {
      Serial.print("[错误] MQTT连接失败，状态码: ");
      Serial.println(client.state());
      
      // 常见错误码说明
      switch(client.state()) {
        case -4: Serial.println("[提示] 网络连接超时"); break;
        case -3: Serial.println("[提示] 服务器不可达"); break;
        case -2: Serial.println("[提示] 协议版本不匹配"); break;
        case -1: Serial.println("[提示] 客户端ID无效"); break;
        case 1: Serial.println("[提示] 不支持的协议版本"); break;
        case 2: Serial.println("[提示] 客户端ID被拒绝"); break;
        case 3: Serial.println("[提示] 服务器不可用"); break;
        case 4: Serial.println("[提示] 用户名/密码错误"); break;
        case 5: Serial.println("[提示] 未授权"); break;
      }
    }
  }
}

// 发送心跳包
void sendHeartbeat() {
  String message = String(NODE_ID) + HEARTBEAT_CODE;
  client.publish(MQTT_TOPIC, message.c_str());
  lastHeartbeat = millis();
  Serial.println("心跳已发送: " + message);
}

// 发送激活包
void sendActivation(char team) {
  String message = String(NODE_ID) + "A" + team;
  client.publish(MQTT_TOPIC, message.c_str());
  Serial.println("激活包已发送: " + message);
}

/**
 * 键盘扫描处理
 * 包含去抖动机制和扫描频率控制
 * 返回检测到的按键字符，无按键时返回'\0'
 */
// 使用Keypad库获取按键并输出状态
char scanKeyboard() {
  char key = keypad.getKey();
  if (key) {
    Serial.print("[键盘状态] 当前按下键: ");
    Serial.print(key);
    Serial.print(" (ASCII ");
    Serial.print((int)key);
    Serial.println(")");
  }
  return key;
}

// 处理键盘输入
void handleInput(char key) {
  static unsigned long inputStart = 0;
  
  if (key == '*' && !isRecording) {
    isRecording = true;
    inputBuffer = "";
    inputStart = millis();
    Serial.println("开始输入激活码...");
    return;
  }

  if (isRecording) {
    if (millis() - inputStart > 30000) {
      isRecording = false;
      Serial.println("输入超时");
      return;
    }
    
    if (key == '*') {
      isRecording = false;
      Serial.println("输入已取消");
      return;
    }

    if (key == '#') {
      isRecording = false;
      Serial.print("[验证] 输入内容: ");
      Serial.println(inputBuffer);
      
      if (inputBuffer.length() == 8 && 
          (inputBuffer[0] >= '1' && inputBuffer[0] <= '4') &&
          inputBuffer.substring(1) == ACTIVATION_CODE) {
        Serial.println("[验证] 激活码格式正确");
        // 将数字1-4转换为A-D发送
        char team = 'A' + (inputBuffer[0] - '1');
        sendActivation(team);
      } else {
        Serial.println("[错误] 无效激活码");
        Serial.println("[提示] 正确格式: [A-D]7355608");
        Serial.print("[诊断] 长度: ");
        Serial.print(inputBuffer.length());
        Serial.print(", 首字符: ");
        Serial.print(inputBuffer[0]);
        Serial.print(", 剩余部分: ");
        Serial.println(inputBuffer.substring(1));
      }
    } else if (inputBuffer.length() < 8) { // 允许输入8个字符（1字母+7数字）
      inputBuffer += key;
      Serial.print("[输入] 当前长度: ");
      Serial.println(inputBuffer.length());
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("[系统] 初始化中...");

  // 初始化硬件
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); // 初始关闭LED
  
  // Keypad库自动初始化键盘引脚
  Serial.println("[硬件] 键盘初始化完成");

  // 初始化看门狗
  ESP.wdtEnable(8000); // 8秒超时
  watchdogTicker.attach(5, feedWatchdog); // 每5秒喂狗
  Serial.println("[系统] 看门狗已启用");

  // 网络连接
  setupWiFi();
  client.setServer(MQTT_SERVER, MQTT_PORT);
  
  Serial.println("[系统] 初始化完成，等待输入...");
}

void loop() {
  ESP.wdtFeed();
  
  // 网络维护
  if (WiFi.status() != WL_CONNECTED) setupWiFi();
  if (!client.connected()) connectMQTT();
  client.loop();

  // 心跳检测
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
  }

  // 键盘处理
  char key = scanKeyboard();
  if (key) handleInput(key);

  delay(1);
}
