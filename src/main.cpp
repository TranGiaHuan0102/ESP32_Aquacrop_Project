#include <Arduino.h>
#include <ArduinoJSON.h>
#include <math.h>
#include <AdafruitIO_WiFi.h>
#include <WiFi.h>
#include <SPI.h>

// Self implemented 
#include <watering.h>
#include <config.h>

#define SOIL_MOISTURE_PIN 34  // Use GPIO34 for analog input of soil moisture sensor
#define PIN_WIRE_SCL 26 // Use GPIO26 for digital output  of relay

void connectWiFi()
{
    Serial.println("Connecting to WiFi...");

    WiFi.disconnect(true);
    delay(1000);

    WiFi.begin(SSID, PASSWORD);  
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {  // Retry for 20 seconds
        Serial.print(".");
        delay(1000);
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nConnected to WiFi!");   
    } else {
        Serial.println("\nFailed to connect. Check WiFi settings.");
    }
}

WiFiClient espClient;         // Create a WiFi client for ESP32
AdafruitIO_WiFi io(IO_USERNAME, IO_KEY, SSID, PASSWORD);  // Create an instance of the AdafruitIO_WiFi object
AdafruitIO_Feed *soil_moisture_feed = io.feed(SOIL_FEED_NAME); // soil_moisture_feed
AdafruitIO_Feed *relay_command_feed = io.feed(RELAY_FEED_NAME); // relay_command_feed

// Use millis to better handle latency
unsigned long last_connecting_time = 0;  
const long connecting_interval = 1000;

void connect_to_Adafruit() {
  Serial.println("Connecting to Adafruit IO...");
  
  io.connect();

  unsigned long startAttemptTime = millis();

  while (io.status() < AIO_CONNECTED && millis() - startAttemptTime < 5000) {
    if (millis() - last_connecting_time >= connecting_interval) {
        last_connecting_time = millis();
        Serial.print(".");
    }
  }
  Serial.println("Connected to Adafruit IO");
}

void send_telemetry(AdafruitIO_Feed* feed, int soil_moisture){
  Serial.print("Sending message: ");
  Serial.println(soil_moisture);

  feed->save(soil_moisture);
}


void handleCommand(AdafruitIO_Data *data) {
  String command = data->value();
  command.trim();
  command.toLowerCase();  

  Serial.print("Received command: ");
  Serial.println(command);
  

  if (command == "relay_on") {
    digitalWrite(PIN_WIRE_SCL, HIGH);
  } 
  else if (command == "relay_off") {
    digitalWrite(PIN_WIRE_SCL, LOW);
  }
}

void setup() {
    Serial.begin(9600); 

    pinMode(SOIL_MOISTURE_PIN, INPUT);
    pinMode(PIN_WIRE_SCL, OUTPUT);

    connectWiFi();

    connect_to_Adafruit();

    relay_command_feed->onMessage(handleCommand);
    
}

unsigned long last_sensor_read = 0; 
const long telemetry_interval = 10000;  

unsigned long last_reconnect_attempt = 0;
const long reconnect_interval = 5000;

int last_valid_soil_moisture_raw = -1;  // -1 means no valid reading yet
void loop() {

    // Reconnect logic if connection drops, attempt to reconnect once every 5 seconds
    if ((WiFi.status() != WL_CONNECTED || io.status() < AIO_CONNECTED) &&
    millis() - last_reconnect_attempt > reconnect_interval) {
      last_reconnect_attempt = millis();
      connectWiFi();
      connect_to_Adafruit();
    }
    
    io.run();

    if (millis() - last_sensor_read >= telemetry_interval)
    {
      last_sensor_read = millis();

      int raw = analogRead(SOIL_MOISTURE_PIN);    // Read moisture data

      if (check_reading_validity(raw, last_valid_soil_moisture_raw)){
          return;
      }

      int soil_moisture = calculate_soil_moisture_percentage(raw);

      // Sending telemetry
      send_telemetry(soil_moisture_feed, soil_moisture);  
    }
}



