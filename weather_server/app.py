import requests
import time
import os
import math
import pandas as pd
import base64

from datetime import datetime, timedelta
from dotenv import load_dotenv
from aquacrop import AquaCropModel, Soil, Crop, InitialWaterContent
from aquacrop.utils import prepare_weather

# OpenWeatherMap config
if os.getenv("GITHUB_ACTIONS") != "true":    
    load_dotenv(dotenv_path='env/weather.env')
    load_dotenv(dotenv_path='env/adafruit.env')

API_KEY = os.getenv("API_KEY")
CITY = os.getenv("CITY")
COUNTRY_CODE = os.getenv("COUNTRY_CODE")
API_URL = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY},{COUNTRY_CODE}&appid={API_KEY}&units=metric"

ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")
RAIN_FEED = os.getenv("RAIN_FEED")
TEMP_FEED = os.getenv("TEMP_FEED")
ICON_FEED = os.getenv("ICON_FEED")
AIO_BASE_URL = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}/feeds"

def calculate_eto_hargreaves(tmax, tmin, tmean, ra):
    """
    Calculate ETo using Hargreaves equation (simplified version)
    tmax, tmin, tmean: temperatures in Celsius
    ra: extraterrestrial radiation in MJ/m²/day
    Returns ETo in mm/day
    """
    # Hargreaves equation: ETo = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * Ra
    if tmax <= tmin:
        return 0.0
    
    eto = 0.0023 * (tmean + 17.8) * math.sqrt(tmax - tmin) * ra
    return max(0, eto)

def get_extraterrestrial_radiation(latitude, day_of_year):
    """
    Calculate extraterrestrial radiation (Ra) in MJ/m²/day
    latitude: in decimal degrees
    day_of_year: julian day (1-365)
    """
    # Convert latitude to radians
    lat_rad = math.radians(latitude)
    
    # Solar declination
    declination = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    
    # Sunset hour angle
    ws = math.acos(-math.tan(lat_rad) * math.tan(declination))
    
    # Distance factor
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    
    # Extraterrestrial radiation
    ra = (24 * 60 / math.pi) * 0.082 * dr * (
        ws * math.sin(lat_rad) * math.sin(declination) + 
        math.cos(lat_rad) * math.cos(declination) * math.sin(ws)
    )
    
    return ra

def fetch_weather_forecast():
    """
    Fetch 5-7 days weather forecast and format into list of dictionaries
    Returns: List of dictionaries with date as key and weather data as values
    """
    try:
        response = requests.get(API_URL)
        data = response.json()
        
        # Get city coordinates for Ra calculation
        latitude = data["city"]["coord"]["lat"]
        
        # Group forecast data by date
        daily_data = {}
        
        for entry in data["list"]:
            # Parse date
            dt = datetime.fromtimestamp(entry["dt"])
            date_str = dt.strftime("%Y-%m-%d")
            
            # Initialize daily data if not exists
            if date_str not in daily_data:
                daily_data[date_str] = {
                    "temps": [],
                    "precipitation": 0.0,
                    "humidity": [],
                    "wind_speed": [],
                    "datetime_obj": dt
                }
            
            # Collect temperature data
            daily_data[date_str]["temps"].append(entry["main"]["temp"])
            
            # Accumulate precipitation (3-hour periods)
            rain = entry.get("rain", {}).get("3h", 0.0)
            snow = entry.get("snow", {}).get("3h", 0.0)
            daily_data[date_str]["precipitation"] += (rain + snow)
            
            # Collect other meteorological data
            daily_data[date_str]["humidity"].append(entry["main"]["humidity"])
            daily_data[date_str]["wind_speed"].append(entry["wind"]["speed"])
        
        # Process daily data and calculate ETo
        forecast_list = []
        
        for date_str, day_data in daily_data.items():
            if len(day_data["temps"]) < 3:  # Skip days with insufficient data
                continue
                
            # Calculate daily temperature statistics
            tmax = max(day_data["temps"])
            tmin = min(day_data["temps"])
            tmean = sum(day_data["temps"]) / len(day_data["temps"])
            
            # Get day of year for Ra calculation
            day_of_year = day_data["datetime_obj"].timetuple().tm_yday
            
            # Calculate extraterrestrial radiation
            ra = get_extraterrestrial_radiation(latitude, day_of_year)
            
            # Calculate ETo using Hargreaves method
            eto = calculate_eto_hargreaves(tmax, tmin, tmean, ra)
            
            # Create daily weather dictionary
            daily_weather = {
                date_str: {
                    "tmax": round(tmax, 2),
                    "tmin": round(tmin, 2),
                    "precipitation": round(day_data["precipitation"], 2),
                    "eto": round(eto, 2)
                }
            }
            
            forecast_list.append(daily_weather)
        
        # Sort by date and return first 5-7 days
        forecast_list.sort(key=lambda x: list(x.keys())[0])
        return forecast_list[:7]  # Return up to 7 days
        
    except Exception as e:
        print(f"Error fetching weather forecast: {e}")
        return []

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

def write_forecast_data(forecast_data, base_dir="climate_data"):
    """
    Write forecast data to .txt files with max 7 entries per file
    Creates new files when current file reaches 7 entries
    Prevents duplicate entries by checking existing dates
    """
    if not forecast_data:
        print("No forecast data to write")
        return None

    # Ensure directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    # Get all existing weather files and find the latest one
    weather_files = [f for f in os.listdir(base_dir) if f.startswith('weather_') and f.endswith('.txt')]
    
    current_file = None
    current_entries = 0
    existing_dates = set()
    
    if weather_files:
        # Sort by modification time to get the latest file
        weather_files.sort(key=lambda x: os.path.getmtime(os.path.join(base_dir, x)), reverse=True)
        latest_file = weather_files[0]
        latest_path = os.path.join(base_dir, latest_file)
        
        # Read existing file to get current entries and dates
        try:
            with open(latest_path, 'r') as f:
                lines = f.readlines()
                current_entries = len(lines) - 1  # subtract header

                # Extract existing dates (skip header)
                for line in lines[1:]:
                    if line.strip():
                        parts = line.strip().split('\t')
                        if len(parts) >= 3:
                            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                            existing_dates.add((day, month, year))
        except:
            current_entries = 0
            existing_dates = set()
        
        if current_entries < 7:
            current_file = latest_path
            print(f"Found existing file with {current_entries} entries: {latest_file}")
    
    # Convert forecast data to the required format
    formatted_data = []
    for day_dict in forecast_data:
        for date_str, weather in day_dict.items():
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_tuple = (dt.day, dt.month, dt.year)
            
            # Only add if date doesn't already exist
            if date_tuple not in existing_dates:
                formatted_data.append({
                    'day': dt.day,
                    'month': dt.month,
                    'year': dt.year,
                    'tmin': weather['tmin'],
                    'tmax': weather['tmax'],
                    'prcp': weather['precipitation'],
                    'eto': weather['eto']
                })
            else:
                print(f"Skipping duplicate date: {dt.day}/{dt.month}/{dt.year}")
    
    if not formatted_data:
        print("No new data to write (all dates already exist)")
        return True
    
    # Determine how many entries we can add to current file
    if current_file and current_entries < 7:
        entries_to_add = min(len(formatted_data), 7 - current_entries)
        
        # Append to existing file
        with open(current_file, 'a') as f:
            for i in range(entries_to_add):
                data = formatted_data[i]
                line = f"{data['day']}\t{data['month']}\t{data['year']}\t{data['tmin']}\t{data['tmax']}\t{data['prcp']}\t{data['eto']}"
                # Add newline except for the last entry if it would make the file complete (7 entries)
                if i < entries_to_add - 1 or (current_entries + entries_to_add) < 7:
                    line += "\n"
                f.write(line)
        
        print(f"Added {entries_to_add} new entries to {current_file}")
        
        # Remove processed entries
        formatted_data = formatted_data[entries_to_add:]
    
    # Create new files for remaining data
    while formatted_data:
        # Take up to 7 entries for new file
        batch = formatted_data[:7]
        formatted_data = formatted_data[7:]
        
        # Create filename based on first date in batch
        first_date = f"{batch[0]['year']}-{batch[0]['month']:02d}-{batch[0]['day']:02d}"
        filename = f"weather_{first_date}.txt"
        filepath = os.path.join(base_dir, filename)
        
        # Write new file
        with open(filepath, 'w') as f:
            # Write header
            f.write("Day\tMonth\tYear\tTmin(C)\tTmax(C)\tPrcp(mm)\tEt0(mm)\n")
            
            # Write data
            for data in batch:
                f.write(f"{data['day']}\t{data['month']}\t{data['year']}\t{data['tmin']}\t{data['tmax']}\t{data['prcp']}\t{data['eto']}\n")
        
        print(f"Created new file: {filename} with {len(batch)} entries")
    
    return True

def run_simulation(base_dir="climate_data", days_ahead=6):
    """
    Find the next 5 days of weather data and run AquaCrop simulation
    Handles edge cases where data may span across multiple files
    """
    try:
        # Get current date (tomorrow since forecasts start from tomorrow)
        today = datetime.now()
        target_dates = [(today + timedelta(days=i)).date() for i in range(days_ahead)]   # Convert to date object
        
        print(f"Looking for data from {target_dates[0].strftime('%Y-%m-%d')} to {target_dates[-1].strftime('%Y-%m-%d')}")

         # Get all weather files sorted by date
        weather_files = [f for f in os.listdir(base_dir) if f.startswith('weather_') and f.endswith('.txt')]
        if not weather_files:
            print("No weather files found!")
            return None
        
        # Sort files by the date in filename
        def extract_date_from_filename(filename):
            # Extract date from format: weather_YYYY-MM-DD.txt
            date_str = filename.replace('weather_', '').replace('.txt', '')
            return datetime.strptime(date_str, '%Y-%m-%d')
        
        weather_files.sort(key=extract_date_from_filename)

        def get_relevant_files(weather_files, target_dates):
            """
            Filter weather files to only those that could contain our target dates using binary search.
            Each file contains 7 days starting from the date in its filename.
            Since files are sorted by date, we can use binary search for efficiency.
            """
            if not target_dates:
                return []
            
            min_target = min(target_dates)
            max_target = max(target_dates)
            
            # Binary search to find the first file that could contain our data
            # We need files where file_end_date >= min_target
            left, right = 0, len(weather_files) - 1
            first_relevant = len(weather_files)  # Default to "not found"
            
            while left <= right:
                mid = (left + right) // 2
                file_start_date = extract_date_from_filename(weather_files[mid]).date()
                file_end_date = file_start_date + timedelta(days=6)
                
                if file_end_date >= min_target:
                    first_relevant = mid
                    right = mid - 1  # Look for earlier files
                else:
                    left = mid + 1
            
            # Binary search to find the last file that could contain our data
            # We need files where file_start_date <= max_target
            left, right = 0, len(weather_files) - 1
            last_relevant = -1  # Default to "not found"
            
            while left <= right:
                mid = (left + right) // 2
                file_start_date = extract_date_from_filename(weather_files[mid]).date()
                
                if file_start_date <= max_target:
                    last_relevant = mid
                    left = mid + 1  # Look for later files
                else:
                    right = mid - 1
            
            # Return the slice of relevant files
            if first_relevant <= last_relevant:
                return weather_files[first_relevant:last_relevant + 1]
            else:
                return []

        # Get only the files that could contain our target dates
        relevant_files = get_relevant_files(weather_files, target_dates)

        # Collect data for the next 5 days
        collected_data = []
        
        for weather_file in relevant_files:
            filepath = os.path.join(base_dir, weather_file)
            try:
                # Read the file
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                # Skip header and process data lines
                for line in lines[1:]:
                    if line.strip():
                        parts = line.strip().split('\t')
                        if len(parts) >= 7:
                            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                            entry_date = datetime(year, month, day).date()  # Convert to date object
                            # Check if this date is in our target range
                            if entry_date in target_dates:
                                collected_data.append({
                                    'date': entry_date,
                                    'day': day,
                                    'month': month,
                                    'year': year,
                                    'tmin': float(parts[3]),
                                    'tmax': float(parts[4]),
                                    'prcp': float(parts[5]),
                                    'eto': float(parts[6])
                                })
                                print(f"Found data for {entry_date.strftime('%Y-%m-%d')} in {weather_file}")
            except Exception as e:
                print(f"Error reading {weather_file}: {e}")
                continue

        

        # Check if we have enough data
        if len(collected_data) < days_ahead:
            print(f"Warning: Only found {len(collected_data)} days of data, need {days_ahead}")
            if len(collected_data) == 0:
                print("No data found for the target dates")
                return None
        
        # Sort collected data by date
        collected_data.sort(key=lambda x: x['date'])

        # Create temporary weather file for AquaCrop
        temp_weather_file = os.path.join(base_dir, "temp_aquacrop_weather.txt")

        with open(temp_weather_file, 'w') as f:
            # Write header
            f.write("Day\tMonth\tYear\tTmin(C)\tTmax(C)\tPrcp(mm)\tEt0(mm)\n")
            
            # Write data
            for i, data in enumerate(collected_data):
                line = f"{data['day']}\t{data['month']}\t{data['year']}\t{data['tmin']}\t{data['tmax']}\t{data['prcp']}\t{data['eto']}"
                if i < len(collected_data) - 1:
                    line += "\n"
                f.write(line)
        
        print(f"Created temporary weather file with {len(collected_data)} days of data")
        
        # Run aquacrop simulation on weather file
        aquacrop_simulation(temp_weather_file)

        # Remove temp_aquacrop
        os.remove(temp_weather_file)

    except Exception as e:
        print(f"Error in aquacrop_process: {e}")
        return None

def aquacrop_simulation(filepath):
    # Prepare weather data for AquaCrop
    weather_df = prepare_weather(filepath)

    # Define Soil type
    sandy_loam = Soil(soil_type='SandyLoam')

    # Define InitWC value 
    InitWC = InitialWaterContent(value=['FC'])

     # Get start and end dates
    start_day = weather_df["Date"].iloc[0]
    final_day = weather_df["Date"].iloc[-1]

    # Planting date 
    planting_date = start_day.strftime("06/14")
    wheat = Crop('Maize', planting_date=planting_date)

    # Combine into aquacrop model
    sim_start_date = start_day.strftime("%Y/%m/%d")
    sim_end_date = final_day.strftime("%Y/%m/%d")

    print(f"Running AquaCrop simulation from {sim_start_date} to {sim_end_date}")

    model = AquaCropModel(sim_start_time=sim_start_date,
                              sim_end_time=sim_end_date,
                              weather_df=weather_df,
                              soil=sandy_loam,
                              crop=wheat,
                              initial_water_content=InitWC)
    
    # Run model till termination
    model.run_model(till_termination=True)

    # Get water flux results 
    water_flux_results = model._outputs.water_flux[model._outputs.water_flux["dap"] != 0].tail(10)
    print("AquaCrop simulation completed!")
    print(water_flux_results)
        
def main():
    print("Fetching 5-7 day weather forecast...")
    
    # Get forecast data
    forecast_data = fetch_weather_forecast()
    
    if forecast_data:
        print(f"Retrieved {len(forecast_data)} days of forecast data:")
        for day_dict in forecast_data:
            for date, weather in day_dict.items():
                print(f"{date}: Tmax={weather['tmax']}°C, Tmin={weather['tmin']}°C, "
                      f"Precip={weather['precipitation']}mm, ETo={weather['eto']}mm")
        
        # Write forecast data to files
        write_forecast_data(forecast_data)
        
        # For Adafruit integration, you can still send today's data
        if forecast_data:
            today_data = list(forecast_data[0].values())[0]
            send_to_adafruit(RAIN_FEED, today_data['precipitation'])
            send_to_adafruit(TEMP_FEED, (today_data['tmax'] + today_data['tmin']) / 2)
            # You can add ETo feed if needed
            
    else:
        print("Failed to fetch forecast data.")

    run_simulation()

if __name__ == "__main__":
    main()