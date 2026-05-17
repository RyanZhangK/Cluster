#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

/******************** 网络配置 ********************/
#define WIFI_SSID "208207"
#define WIFI_PASSWORD "1234567890"

/******************** MQTT配置 ********************/
#define MQTT_SERVER "182.92.87.183"
#define MQTT_PORT 9000
#define MQTT_TOPIC "node/status"
#define MQTT_USER "nodeuser"
#define MQTT_PASSWORD "nodeuserpassword"

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
}

void
setup_wifi()
{
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    blinkLED(1, 100);
    delay(400);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("WiFi connected, IP: ");
  Serial.println(WiFi.localIP());
}

void
reconnect()
{
  while (!client.connected()) {
    Serial.print("Connecting to MQTT ");
    Serial.print(MQTT_SERVER);
    Serial.print(":");
    Serial.print(MQTT_PORT);
    Serial.print(" ... ");

    if (client.connect(NODE_ID, MQTT_USER, MQTT_PASSWORD)) {
      Serial.println("connected");
      client.subscribe(MQTT_TOPIC);
    } else {
      int state = client.state();
      Serial.print("failed, rc=");
      Serial.print(state);
      Serial.println(", retry in 5s");
      blinkLED(5, 200);
      delay(5000);
    }
  }
}

void
callback(char* topic, byte* payload, unsigned int length)
{
  Serial.print("Message [");
  Serial.print(topic);
  Serial.print("]: ");
  for (unsigned int i = 0; i < length; i++)
    Serial.print((char)payload[i]);
  Serial.println();
}

void
send_heartbeat()
{
  String msg = String(NODE_ID) + HEARTBEAT_CODE;
  client.publish(MQTT_TOPIC, msg.c_str());
  Serial.println("Heartbeat: " + msg);
}

void
send_activation()
{
  String msg = String(NODE_ID) + ACTIVATION_CODE;
  client.publish(MQTT_TOPIC, msg.c_str());
  Serial.println("Activation: " + msg);
}

void
setup()
{
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  Serial.begin(115200);
  delay(100);
  Serial.println("\n\n--- STA Node Starting ---");
  Serial.print("Node ID: ");
  Serial.println(NODE_ID);

  blinkLED(2, 50);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  setup_wifi();

  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(callback);
  reconnect();

  send_heartbeat();
  last_heartbeat = millis();
  Serial.println("Setup complete");
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
  int buttonState = digitalRead(BUTTON_PIN);

  if (buttonState != lastButtonState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > 50 && buttonState == LOW) {
    blinkLED(3, 50);
    send_activation();
    while (digitalRead(BUTTON_PIN) == LOW)
      delay(10);
    blinkLED(1, 50);
  }

  lastButtonState = buttonState;
  delay(10);
}
