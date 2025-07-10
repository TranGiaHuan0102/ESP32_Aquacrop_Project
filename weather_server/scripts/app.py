import requests
import os

from datetime import datetime
from dotenv import load_dotenv
from paths import get_server_root
from mongodb import get_database
from weather import write_forecast_data
from simulation import run_simulation

# OpenWeatherMap config
if os.getenv("GITHUB_ACTIONS") != "true":
    server_root = get_server_root()    
    load_dotenv(dotenv_path=server_root / 'env/adafruit.env')

ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")
RAIN_FEED = os.getenv("RAIN_FEED")
TEMP_FEED = os.getenv("TEMP_FEED")
ET0_FEED = os.getenv("ET0_FEED")
DAY_FEED = os.getenv("DAY_FEED")
DECISION_FEED = os.getenv("DECISION_FEED")
AIO_BASE_URL = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds"

def update_today_weather():
    today = datetime.now()
    
    today_weather = get_database(start_date=today, end_date=today)[0]      # [{"weather": {}}]

    return today_weather["weather"]

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
    # Step 1: Update weather data
    write_forecast_data()

    # Step 2: Get today's data and run simulation
    today_weather = update_today_weather()
    irrigation_decison = run_simulation()       # Simulation returns a boolean value
    
    if today_weather:
        send_to_adafruit(RAIN_FEED, today_weather['prcp'])
        send_to_adafruit(TEMP_FEED, ((today_weather['tmin'] + today_weather['tmax']) / 2))
        send_to_adafruit(ET0_FEED, today_weather["eto"])
        send_to_adafruit(DAY_FEED, today_weather["datetime"])
        if irrigation_decison:
            send_to_adafruit(DECISION_FEED, "ON")
        else:
            send_to_adafruit(DECISION_FEED, "OFF")
    else:
        print("Failing to fetch today's weather data!")

if __name__ == '__main__':
    main()