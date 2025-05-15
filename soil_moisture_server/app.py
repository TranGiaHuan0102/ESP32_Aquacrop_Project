import json
import time 
import threading
import os
from Adafruit_IO import MQTTClient
from dotenv import load_dotenv

load_dotenv() # Load variables from .env

# Adafruit Credentials
USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
AIO_KEY = os.getenv("ADAFRUIT_IO_KEY")

# Feed names
MOISTURE_FEED = "soil-moisture"
RELAY_FEED = 'relay-command'

# Config for toggling relay on/off
DRYNESS_THRESHOLD = 15  # Moisture percentage
water_time = 5          # How long to water (seconds)
wait_time = 20          # Time to wait before listening again

# Global flag to avoid duplicate triggers
watering_event = threading.Event()      # Flag is off by default (False)

# Create Adafruit IO client
aio_client = MQTTClient(USERNAME, AIO_KEY)


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



# Set up callbacks
aio_client.on_connect = lambda client : client.subscribe(MOISTURE_FEED)
aio_client.on_message = handle_moisture_feed

# Connect server to AdafruitIO
print(("🔗 Connecting to Adafruit IO..."))
aio_client.connect()
aio_client.loop_blocking()  # Start listening


