#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <NTPClient.h>
#include <DHT.h>
#include <ESP8266WebServer.h>
#include <LittleFS.h>


const char* ssid = "Destroyer055";
const char* password = "as20130129as";

// 定义引脚
#define TFT_CS   15
#define TFT_RST  0
#define TFT_DC   2

Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

// NTP 客户端配置（东京时区）
WiFiUDP udp;
NTPClient timeClient(udp, "pool.ntp.org", 3600 * 9, 3600000); // UTC+9时区

// DHT11 配置
#define DHTPIN 5  // D2
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// 风扇和LED配置
int ledPin = 16;  // D0
int fanPin = 4;   // D1

// Web 服务器
ESP8266WebServer server(80);

void setup() {
  Serial.begin(9600);

  // 初始化引脚
  pinMode(ledPin, OUTPUT);
  pinMode(fanPin, OUTPUT);
  digitalWrite(ledPin, HIGH);  // LED初始化为关闭
  digitalWrite(fanPin, LOW);   // 风扇初始化为关闭

  // 初始化DHT传感器
  dht.begin();

  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("Connected to WiFi");


  timeClient.begin();


  tft.initR(INITR_BLACKTAB);
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(2);


  if (!LittleFS.begin()) {
    Serial.println("Failed to mount file system");
    return;
  }

  // 首页路由
  server.on("/", HTTP_GET, []() {
    File file = LittleFS.open("/index.html", "r");
    if (!file) {
      server.send(404, "text/plain", "File not found");
      return;
    }
    server.streamFile(file, "text/html");
    file.close();
  });

  // LED控制路由
  server.on("/LED", HTTP_POST, []() {
    String action = server.arg("action");
    if (action == "on") {
      digitalWrite(ledPin, LOW); // LED开启
      server.send(200, "text/plain", "LED turned on");
    } else if (action == "off") {
      digitalWrite(ledPin, HIGH); // LED关闭
      server.send(200, "text/plain", "LED turned off");
    } else {
      server.send(400, "text/plain", "Invalid action");
    }
  });


  server.on("/getData", HTTP_GET, []() {
    float temperature = dht.readTemperature();
    if (isnan(temperature)) {
      server.send(500, "application/json", "{\"error\":\"Failed to read temperature\"}");
      return;
    }
    String jsonData = "{\"temperature\":" + String(temperature) + "}";
    server.send(200, "application/json", jsonData);
  });


  server.on("/fanControl", HTTP_POST, []() {
    String action = server.arg("action");
    if (action == "on") {
      digitalWrite(fanPin, HIGH); // 风扇开启
      server.send(200, "text/plain", "Fan turned on");
    } else if (action == "off") {
      digitalWrite(fanPin, LOW);  // 风扇关闭
      server.send(200, "text/plain", "Fan turned off");
    } else {
      server.send(400, "text/plain", "Invalid action");
    }
  });

  server.onNotFound([]() {
    server.send(404, "text/plain", "404: Not Found");
  });

  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  // 更新NTP时间
  timeClient.update();

  // 获取温度数据
  float temperature = dht.readTemperature();
  if (isnan(temperature)) {
    temperature = 0;  // 读取失败时显示0°C
  }

  // 显示时间、温度、LED和风扇状态
  tft.fillScreen(ST77XX_BLACK);
  tft.setCursor(10, 30);

  // 显示时间
  String currentTime = timeStr();
  tft.println("Time: ");
  tft.println(currentTime);

  // 显示温度
  tft.setCursor(10, 60);
  tft.print("Temp: ");
  tft.print(temperature);
  tft.println(" C");

  // 显示风扇状态
  tft.setCursor(10, 90);
  if (digitalRead(fanPin) == HIGH) {
    tft.println("Fan: ON");
  } else {
    tft.println("Fan: OFF");
  }

  // 显示LED状态
  tft.setCursor(10, 120);
  if (digitalRead(ledPin) == LOW) {
    tft.println("LED: ON");
  } else {
    tft.println("LED: OFF");
  }

  delay(1000); // 每秒更新一次

  // 处理Web请求
  server.handleClient();
}

// 获取NTP时间并格式化为字符串
String timeStr() {
  char buf[9];
  snprintf(buf, sizeof(buf), "%02d:%02d:%02d", timeClient.getHours(), timeClient.getMinutes(), timeClient.getSeconds());
  return String(buf);
}
