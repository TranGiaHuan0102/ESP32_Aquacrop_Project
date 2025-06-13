import requests
import os
import math

from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

def get_server_root():
    # Get the directory where this script is located
    return Path(__file__).resolve().parent.parent

def get_climate_data_path():
    return str(get_server_root() / "climate_data")

# OpenWeatherMap config
if os.getenv("GITHUB_ACTIONS") != "true":
    server_root = get_server_root()    
    load_dotenv(dotenv_path=server_root / 'env/OpenWeather.env')


API_KEY = os.getenv("API_KEY")
CITY = os.getenv("CITY")
COUNTRY_CODE = os.getenv("COUNTRY_CODE")
API_URL = f"http://api.openweathermap.org/data/2.5/forecast?q={CITY},{COUNTRY_CODE}&appid={API_KEY}&units=metric"

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

def write_forecast_data(forecast_data, base_dir=None):
    """
    Write forecast data to .txt files with max 7 entries per file
    Creates new files when current file reaches 7 entries
    Prevents duplicate entries by checking existing dates
    """
    if base_dir is None:
        base_dir = get_climate_data_path()

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
    else:
        print("Failed to fetch forecast data.")

if __name__ == "__main__":
    main()