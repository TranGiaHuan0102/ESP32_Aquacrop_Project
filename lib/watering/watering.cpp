#include <watering.h>
#include <Arduino.h>

int calculate_soil_moisture_percentage(int soil_moisture){
    soil_moisture = constrain(soil_moisture, 0, ABSOLUTE_DRYNESS);  // Force soil_moisture to be within 0 and 4095
    return map(soil_moisture, ABSOLUTE_DRYNESS, 0, 0, 100);
}

bool check_reading_validity(int raw, int last_reading){
    // Too high and too low
    bool suspicious_high = (raw >= SENSOR_DISCONNECT_THRESHOLD);
    bool suspicious_low = raw <= SENSOR_MIN_VALID_THRESHOLD;

    // Sensor disconnected case. 
    if ((suspicious_high || suspicious_low) && last_reading == -1){
        Serial.println("⚠️ Initial sensor noise or disconnected. Skipping.");
        return false;
    }

    // If it looks suspicious *and* differs too much from the last valid value
    if ((suspicious_high || suspicious_low) && last_reading != -1) {
        int diff = abs(raw - last_reading);
        if (diff > 500) {  // You can adjust this threshold
            Serial.print("⚠️ Ignoring outlier reading: ");
            Serial.println(raw);
            return false;
        }
    }
    return true;
}