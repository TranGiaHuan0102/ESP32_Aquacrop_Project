import requests
import os

from datetime import datetime, timedelta
from dotenv import load_dotenv
from paths import get_server_root, get_climate_data_path

# OpenWeatherMap config
if os.getenv("GITHUB_ACTIONS") != "true":
    server_root = get_server_root()    
    load_dotenv(dotenv_path=server_root / 'env/adafruit.env')

ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")
RAIN_FEED = os.getenv("RAIN_FEED")
TEMP_FEED = os.getenv("TEMP_FEED")
ICON_FEED = os.getenv("ICON_FEED")
AIO_BASE_URL = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds"

def update_today_weather(base_dir=get_climate_data_path()):
    # Find the file that contains today's data
    try:
        # Get all weather files sorted by date
        weather_files = [f for f in os.listdir(base_dir) if f.startswith('weather_') and f.endswith('.txt')]

        # Sort files by the date in filename
        def extract_date_from_filename(filename):
            # Extract date from format: weather_YYYY-MM-DD.txt
            date_str = filename.replace('weather_', '').replace('.txt', '')
            return datetime.strptime(date_str, '%Y-%m-%d')
        
        weather_files.sort(key=extract_date_from_filename)

        def get_relevant_files(weather_files, today=datetime.now()):
            target_date = today.date()
            left, right = 0, len(weather_files) - 1

            # Binary search to find the first file that could contain our data

            while left <= right:
                mid = (left + right) // 2
                file_start_date = extract_date_from_filename(weather_files[mid]).date()
                file_end_date = file_start_date + timedelta(days=6)  
                
                # Check if target_date falls within this file's range
                if file_start_date <= target_date <= file_end_date:
                    return weather_files[mid]  # Found the file containing today's data
                elif target_date < file_start_date:
                    right = mid - 1            # Target is before this file, search left half
                else:  # target_date > file_end_date
                    left = mid + 1             # Target is after this file, search right half

            # If we get here, no file contains today's data
            return None
    except Exception as e:
        print("Data folder not found!")
        return None
    
    try:
        filepath = f"{base_dir}/{get_relevant_files(weather_files)}"

        # Read the file and check if today's data exists
        today = datetime.now()
        target_day = today.day
        target_month = today.month
        target_year = today.year
        
        with open(filepath, 'r') as file:
            lines = file.readlines()
            
        # Skip header line
        if len(lines) < 2:
            print("File is empty or only contains header")
            return None
            
        # Parse each data line to find today's entry
        for line in lines[1:]:  # Skip header
            line = line.strip()
            if not line:  # Skip empty lines
                continue
                
            try:
                # Split the line into columns
                parts = line.split('\t')
                if len(parts) < 7:  # Should have at least 7 columns
                    continue
                    
                day = int(parts[0])
                month = int(parts[1])
                year = int(parts[2])
                tmin = float(parts[3])
                tmax = float(parts[4])
                prcp = float(parts[5])
                et0 = float(parts[6])
                
                # Check if this is today's data
                if day == target_day and month == target_month and year == target_year:
                    return {
                        'Tmin': tmin,
                        'Tmax': tmax,
                        'Prcp': prcp,
                        'Et0': et0
                    }
                    
            except (ValueError, IndexError) as e:
                # Skip malformed lines
                continue
        
        # If we get here, today's data was not found in the file
        print(f"Today's data ({target_day}/{target_month}/{target_year}) not found in file")
        return None
    except Exception as e:
        print("Error accessing datafile")
        return None


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
    today_weather = update_today_weather()

    if today_weather:
        send_to_adafruit(RAIN_FEED, today_weather['Prcp'])
        send_to_adafruit(TEMP_FEED, ((today_weather['Tmin'] + today_weather['Tmax']) / 2))
    else:
        print("Failing to fetch today's weather data!")
if __name__ == '__main__':
    main()