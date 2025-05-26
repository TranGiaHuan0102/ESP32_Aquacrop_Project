#ifndef WATERING_H
#define WATERING_H

#define ABSOLUTE_DRYNESS 4095

const int SENSOR_DISCONNECT_THRESHOLD = ABSOLUTE_DRYNESS - 20; 
const int SENSOR_MIN_VALID_THRESHOLD = 10;          

int calculate_soil_moisture_percentage(int soil_moisture);
bool check_reading_validity(int raw, int last_reading);
#endif