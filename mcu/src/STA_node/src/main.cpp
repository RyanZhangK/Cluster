#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

/******************** 调试开关 ********************/
#define DEBUG false

#if DEBUG
#define LOG_PRINT(x) Serial.print(x)
#define LOG_PRINTLN(x) Serial.println(x)
#else
#define LOG_PRINT(x)
#define LOG_PRINTLN(x)
#endif

/******************** 网络配置 ********************/
#ifndef WIFI_SSID
#define WIFI_SSID "ZG"

#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "ZG888888"
#endif

/******************** MQTT配置 ********************/
#ifndef MQTT_SERVER
#define MQTT_SERVER "182.92.87.183"
#endif
#define MQTT_PORT 9001
#define MQTT_TOPIC "node/status"
#define MQTT_CMD_TOPIC "node/command"

/******************** 节点配置 ********************/
#define NODE_ID "STA01"
#define BUTTON_PIN D1
#define LED_PIN D4
#define HEARTBEAT_INTERVAL 180000

/******************** 报文配置 ********************/
#define HEARTBEAT_CODE "H0"
#define ACTIVATION_CODE "A1"

WiFiClient espClient;
PubSubClient client(espClient);
unsigned long last_heartbeat = 0;
bool venue_locked = false;

void
blinkLED(int times = 1, int duration = 100)
{
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, LOW);
    delay(duration);
    digitalWrite(LED_PIN, HIGH);
    if (i < times - 1)
      delay(duration);
  }
  // Restore lock-state LED indicator
  digitalWrite(LED_PIN, venue_locked ? HIGH : LOW);
}

void
setup_wifi()
{
  LOG_PRINT("Connecting to WiFi: ");
  LOG_PRINTLN(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    blinkLED(1, 100);
    delay(400);
    LOG_PRINT(".");
  }

  LOG_PRINTLN("");
  LOG_PRINT("WiFi connected, IP: ");
  LOG_PRINTLN(WiFi.localIP());
}

void
reconnect()
{
  while (!client.connected()) {
    if (WiFi.status() != WL_CONNECTED) {
      LOG_PRINTLN("WiFi disconnected, reconnecting...");
      setup_wifi();
    }

    LOG_PRINT("Connecting to MQTT ");
    LOG_PRINT(MQTT_SERVER);
    LOG_PRINT(":");
    LOG_PRINT(MQTT_PORT);
    LOG_PRINT(" ... ");

    if (client.connect(NODE_ID)) {
      LOG_PRINTLN("connected");
      client.subscribe(MQTT_TOPIC);
      client.subscribe(MQTT_CMD_TOPIC);
    } else {
      int state = client.state();
      LOG_PRINT("failed, rc=");
      LOG_PRINT(state);
      LOG_PRINTLN(", retry in 500ms");
      blinkLED(1, 100);
      for (int i = 0; i < 10; i++) {
        delay(50);
        client.loop();
      }
    }
  }
}

void
callback(char* topic, byte* payload, unsigned int length)
{
  // 构建以 null 结尾的字符串
  char msg[16] = { 0 };
  unsigned int copy_len =
    length < (sizeof(msg) - 1) ? length : (sizeof(msg) - 1);
  memcpy(msg, payload, copy_len);

  LOG_PRINT("Message [");
  LOG_PRINT(topic);
  LOG_PRINT("]: ");
  LOG_PRINTLN(msg);

  // 处理场馆锁定命令
  if (strcmp(topic, MQTT_CMD_TOPIC) == 0) {
    if (strcmp(msg, "LOCK:1") == 0) {
      venue_locked = true;
      digitalWrite(LED_PIN, HIGH); // LED 熄灭（active-LOW）
      LOG_PRINTLN("Venue LOCKED");
    } else if (strcmp(msg, "LOCK:0") == 0) {
      venue_locked = false;
      digitalWrite(LED_PIN, LOW); // LED 亮起（active-LOW）
      LOG_PRINTLN("Venue UNLOCKED");
    }
  }
}

void
send_heartbeat()
{
  String msg = String(NODE_ID) + HEARTBEAT_CODE;
  client.publish(MQTT_TOPIC, msg.c_str());
  LOG_PRINT("Heartbeat: ");
  LOG_PRINTLN(msg);
}

void
send_activation()
{
  String msg = String(NODE_ID) + ACTIVATION_CODE;
  client.publish(MQTT_TOPIC, msg.c_str());
  LOG_PRINT("Activation: ");
  LOG_PRINTLN(msg);
}

void
setup()
{
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  Serial.begin(115200);
  delay(100);
  LOG_PRINTLN("");
  LOG_PRINTLN("");
  LOG_PRINTLN("--- STA Node Starting ---");
  LOG_PRINT("Node ID: ");
  LOG_PRINTLN(NODE_ID);

  blinkLED(2, 50);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  setup_wifi();

  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(callback);
  reconnect();

  send_heartbeat();
  last_heartbeat = millis();
  LOG_PRINTLN("Setup complete");
}

void
loop()
{
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  if (millis() - last_heartbeat > HEARTBEAT_INTERVAL) {
    blinkLED(2, 50);
    send_heartbeat();
    last_heartbeat = millis();
  }

  static unsigned long lastDebounceTime = 0;
  static int lastButtonState = HIGH;
  static int stableButtonState = HIGH;
  int buttonState = digitalRead(BUTTON_PIN);

  if (buttonState != lastButtonState) {
    lastDebounceTime = millis();
  }

  // 状态稳定 50ms 后才确认
  if ((millis() - lastDebounceTime) > 50) {
    if (buttonState != stableButtonState) {
      stableButtonState = buttonState;
      // 下降沿：按钮按下
      if (stableButtonState == LOW) {
        LOG_PRINTLN("Button pressed!");
        if (venue_locked) {
          LOG_PRINTLN("Venue locked, activation blocked");
        } else {
          blinkLED(3, 50);
          send_activation();
        }
      }
    }
  }

  lastButtonState = buttonState;
  delay(10);
}
