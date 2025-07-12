import os
import time
import threading
import requests
from dotenv import load_dotenv
from paths import get_server_root
from Adafruit_IO import MQTTClient

if os.getenv("GITHUB_ACTIONS") != "true":
    server_root = get_server_root()    
    load_dotenv(dotenv_path=server_root / 'env/adafruit.env')

# Adafruit credentials  
ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")

# Feed names
MOISTURE_FEED = "soil-moisture"
RELAY_FEED = "relay"

# Config for toggling relay on/off
DRYNESS_THRESHOLD = 15  # Moisture percentage
water_time = 5          # How long to water (seconds)
wait_time = 20          # Time to wait before listening again

# Global flag to avoid duplicate triggers
watering_event = threading.Event()      # Flag is off by default (False)

def clear_moisture_feed_with_limit(limit=100):
    try:        
        # Get limited number of datapoints (most recent first)
        get_url = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds/{MOISTURE_FEED}/data?limit={limit}"
        
        headers = {
            'X-AIO-Key': ADAFRUIT_IO_KEY,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(get_url, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch datapoints. Status code: {response.status_code}")
            return
        
        datapoints = response.json()
        
        for datapoint in datapoints:
            try:
                datapoint_id = datapoint['id']
                delete_url = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds/{MOISTURE_FEED}/data/{datapoint_id}"
                
                requests.delete(delete_url, headers=headers)
                
                time.sleep(0.1)  # Rate limit protection
                
            except Exception as e:
                print(f"❌ Error deleting datapoint: {e}")
        
    except Exception as e:
        print(f"❌ Error clearing feed data: {e}")


# Modified on_connect callback - clears data after connecting
def on_connect_with_clear(client):
    '''Clear old data before fresh connection'''

    print("🔗 Connected to Adafruit IO!")
    client.subscribe(MOISTURE_FEED)
    print(f"📡 Subscribed to {MOISTURE_FEED}")

    threading.Thread(target=clear_moisture_feed_with_limit, daemon=True).start()  # Delete ALL data


# Sending relay commands
def send_relay_command(state):
    aio_client.publish(RELAY_FEED, "relay_on" if state else "relay_off")

# Water for 5 seconds then wait for 20 seconds to grab the next sensor read
def control_relay():    
    watering_event.set()  # Lock out other triggers by setting flag to True

    try:
        print("🚿 Soil is dry, watering plant...")
        
        # Watering for 5 seconds
        send_relay_command(True)
        time.sleep(water_time)
        send_relay_command(False)

        # Waiting for 20 seconds
        print(f"🕒 Waiting {wait_time} seconds before resuming...")
        time.sleep(wait_time)
    
    
    finally:
        watering_event.clear()  # Unlock for next trigger

# Anaylise soil moisture percentage then determine whether to turn relay on or off
def handle_moisture_feed(client, feed_id, payload):
    try:
        soil_moisture = int(payload)
        print(f"📩 Received moisture data: {soil_moisture}%")

        # Already watering, ignore this trigger
        if watering_event.is_set():
            print("⏳ Already watering. Ignoring new data.")
            return
        
        if soil_moisture < DRYNESS_THRESHOLD:
            threading.Thread(target=control_relay).start()
    
    except ValueError:
        print("❌ Invalid integer in payload.")



# Create Adafruit IO client
aio_client = MQTTClient(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)

# Set up callbacks
aio_client.on_connect = on_connect_with_clear
aio_client.on_message = handle_moisture_feed


# Connect server to AdafruitIO
print(("🔗 Connecting to Adafruit IO..."))
aio_client.connect()
aio_client.loop_blocking()  # Start listening