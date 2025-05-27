import requests
import time
from dotenv import load_dotenv
import os
import base64

# OpenWeatherMap config
load_dotenv(dotenv_path='env/weather.env')
API_KEY = os.getenv("API_KEY")
CITY = os.getenv("CITY")
COUNTRY_CODE = os.getenv("COUNTRY_CODE")
API_URL = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY},{COUNTRY_CODE}&appid={API_KEY}&units=metric"

# AdafruitIO config
load_dotenv(dotenv_path='env/adafruit.env')
ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")
RAIN_FEED = os.getenv("RAIN_FEED")
TEMP_FEED = os.getenv("TEMP_FEED")
ICON_FEED = os.getenv("ICON_FEED")
AIO_BASE_URL = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds"


def fetch_weather():
    try:
        response = requests.get(API_URL)
        data = response.json()

        total_rain = 0.0
        total_temp = 0.0
        count = 0
        icon_code = ""

        # First 8 entries = ~24 hours (3-hour intervals)
        for i in range(8):
            entry = data["list"][i]

            # Rain (may not be present in all entries)
            rain = entry.get("rain", {}).get("3h", 0.0)
            total_rain += rain

            # Temperature
            temp = entry["main"]["temp"]
            total_temp += temp
            count += 1

            # Grab icon for midday time slot
            if (icon_code == "" and ("12:00:00" in entry["dt_txt"])):
                icon_code = entry["weather"][0]["icon"]

        # If there's no midday, default to the first time slot
        if (icon_code == ""):
            icon_code = data["list"][0]["weather"][0]["icon"]

        avg_temp = total_temp / count if count > 0 else 0.0
        
        return total_rain, avg_temp, icon_code

    except Exception as e:
        print("Error fetching weather data:", e)
        return None, None, None


def send_to_adafruit(feed_key, value):
    url = f"{AIO_BASE_URL}/{feed_key}/data"
    headers = {"X-AIO-Key": ADAFRUIT_IO_KEY, "Content-Type": "application/json"}
    payload = {"value": value}
    
    try:
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            print(f"Failed to send to {feed_key}: {r.text}")
        else:
            print(f"Updated {feed_key}: {value}")
    except Exception as e:
        print(f"Error sending to Adafruit IO: {e}")


def main():
    print("Fetching weather forecast...")

    rain, temp, icon_code = fetch_weather()

    print(f"Using feed keys: Rain={RAIN_FEED}, Temp={TEMP_FEED}, Icon={ICON_FEED}")
    print(f"API Base URL: {AIO_BASE_URL}")
    
    if rain is not None:
        print(f"24h Forecast - Rain: {rain:.2f} mm, Avg Temp: {temp:.2f} °C")
        send_to_adafruit(RAIN_FEED, rain)
        send_to_adafruit(TEMP_FEED, temp)
        send_to_adafruit(ICON_FEED, icon_code)
    else:
        print("Failed to fetch forecast.")

if __name__ == "__main__":
    main()