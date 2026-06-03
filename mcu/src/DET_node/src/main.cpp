#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

#include <Keypad.h>

/******************** 键盘配置 ********************/
const byte ROWS = 4;
const byte COLS = 3;
char keys[ROWS][COLS] = { { '1', '2', '3' },
                          { '4', '5', '6' },
                          { '7', '8', '9' },
                          { '*', '0', '#' } };
byte rowPins[ROWS] = { D1, D2, D3, D4 }; // 行引脚(输出)
byte colPins[COLS] = { D5, D6, D7 }; // 列引脚(输入，内部上拉)

// 初始化Keypad实例
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

/******************** 网络配置 ********************/
#ifndef WIFI_SSID
#define WIFI_SSID "208207"
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "1234567890"
#endif

/******************** MQTT配置 ********************/
#ifndef MQTT_SERVER
#define MQTT_SERVER "182.92.87.183"
#endif
#define MQTT_PORT 9001
#define MQTT_TOPIC "node/status"

/******************** 节点配置 ********************/
#define NODE_ID "DET01"           // 节点识别码
#define HEARTBEAT_INTERVAL 180000 // 心跳间隔(ms)，3分钟=180000ms

/******************** 报文配置 ********************/
#define HEARTBEAT_CODE "H0"   // 心跳报文后缀

// 全局变量
WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastHeartbeat = 0;
String inputBuffer;
bool isRecording = false;

/**
 * 初始化WiFi连接
 * 自动重试直到连接成功，30秒超时自动重启
 */
void
setupWiFi()
{
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startTime = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");

    // 30秒连接超时自动重启
    if (millis() - startTime > 30000) {
      Serial.println();
      Serial.println("WiFi connect timeout, restarting...");
      ESP.restart();
    }
  }

  Serial.println();
  Serial.print("WiFi connected, IP: ");
  Serial.println(WiFi.localIP());
}

/**
 * 连接MQTT服务器（匿名认证）
 * 包含错误状态码输出和自动重试机制
 */
void
connectMQTT()
{
  if (!client.connected()) {
    Serial.print("Connecting to MQTT ");
    Serial.print(MQTT_SERVER);
    Serial.print(":");
    Serial.print(MQTT_PORT);
    Serial.print(" ... ");

    if (client.connect(NODE_ID)) {
      Serial.println("connected");
      client.subscribe(MQTT_TOPIC);
    } else {
      int state = client.state();
      Serial.print("failed, rc=");
      Serial.print(state);

      // 常见错误码说明
      switch (state) {
        case -4: Serial.println(" (connection timeout)"); break;
        case -3: Serial.println(" (server unreachable)"); break;
        case -2: Serial.println(" (protocol mismatch)"); break;
        case -1: Serial.println(" (invalid client ID)"); break;
        case 1:  Serial.println(" (unsupported protocol)"); break;
        case 2:  Serial.println(" (client ID rejected)"); break;
        case 3:  Serial.println(" (server unavailable)"); break;
        case 4:  Serial.println(" (bad username/password)"); break;
        case 5:  Serial.println(" (unauthorized)"); break;
        default: Serial.println(); break;
      }
    }
  }
}

// 发送心跳包
void
sendHeartbeat()
{
  String message = String(NODE_ID) + HEARTBEAT_CODE;
  client.publish(MQTT_TOPIC, message.c_str());
  lastHeartbeat = millis();
  Serial.println("Heartbeat: " + message);
}

// 发送激活包
void
sendActivation(char team)
{
  String message = String(NODE_ID) + "A" + team;
  client.publish(MQTT_TOPIC, message.c_str());
  Serial.println("Activation: " + message);
}

/**
 * 键盘扫描处理
 * 使用Keypad库获取按键，返回检测到的按键字符，无按键时返回'\0'
 */
char
scanKeyboard()
{
  return keypad.getKey();
}

// 处理键盘输入
// * 开始输入, # 结束输入
// 三位重复数字: 111→A队, 222→B队, 333→C队, 444→D队
void
handleInput(char key)
{
  static unsigned long inputStart = 0;

  if (key == '*' && !isRecording) {
    isRecording = true;
    inputBuffer = "";
    inputStart = millis();
    Serial.println("Keypad: input started");
    return;
  }

  if (isRecording) {
    // 30秒超时
    if (millis() - inputStart > 30000) {
      isRecording = false;
      Serial.println("Keypad: input timeout");
      return;
    }

    // * 取消输入
    if (key == '*') {
      isRecording = false;
      Serial.println("Keypad: input cancelled");
      return;
    }

    // # 确认输入
    if (key == '#') {
      isRecording = false;

      // 验证: 必须恰好3个相同数字 (111, 222, 333, 444)
      if (inputBuffer.length() == 3 &&
          inputBuffer[0] == inputBuffer[1] &&
          inputBuffer[1] == inputBuffer[2] &&
          inputBuffer[0] >= '1' && inputBuffer[0] <= '4') {
        char team = 'A' + (inputBuffer[0] - '1');
        Serial.print("Keypad: team ");
        Serial.print(team);
        Serial.print(" (");
        Serial.print(inputBuffer);
        Serial.println(")");
        sendActivation(team);
      }
      // 格式不符合: 静默重置，不响应
      return;
    }

    // 仅收集数字键 (0-9)，忽略 * 和 #
    if (key >= '0' && key <= '9' && inputBuffer.length() < 3) {
      inputBuffer += key;
    }
  }
}

void
setup()
{
  Serial.begin(115200);
  delay(100);
  Serial.println("\n\n--- DET Node Starting ---");
  Serial.print("Node ID: ");
  Serial.println(NODE_ID);

  // 初始化硬件
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); // 初始关闭LED
  Serial.println("Keypad initialized");

  // 初始化看门狗（8秒超时，loop()中手动喂狗）
  ESP.wdtEnable(8000);

  // 网络连接
  setupWiFi();
  client.setServer(MQTT_SERVER, MQTT_PORT);

  Serial.println("Setup complete");
}

void
loop()
{
  ESP.wdtFeed();

  // 网络维护
  if (WiFi.status() != WL_CONNECTED)
    setupWiFi();
  if (!client.connected())
    connectMQTT();
  client.loop();

  // 心跳检测
  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    sendHeartbeat();
  }

  // 键盘处理
  char key = scanKeyboard();
  if (key)
    handleInput(key);

  delay(1);
}
