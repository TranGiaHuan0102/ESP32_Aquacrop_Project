import requests
import os
import math

from datetime import datetime
from dotenv import load_dotenv
from database import get_database_path
from paths import get_climate_data_path, get_server_root
from database import get_database_path, initialize_database, write_to_database, get_from_database

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

def write_forecast_data(forecast_data=None, base_dir=None):
    """
    Write forecast data to SQLite database
    Replaces existing entries for the same date with new data
    Data is automatically sorted by datetime column
    """

    if forecast_data is None:
        forecast_data = fetch_weather_forecast()
        
    # Locate and initialize database
    db_path = get_database_path()
    initialize_database(db_path)

    # Convert forecast data to the required format
    formatted_data = []
    for day_dict in forecast_data:
        for date_str, weather in day_dict.items():
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            datetime_str = dt.strftime("%Y-%m-%d")  # Standardized format
            
            formatted_data.append({
                'day': dt.day,
                'month': dt.month,
                'year': dt.year,
                'datetime': datetime_str,
                'tmin': weather['tmin'],
                'tmax': weather['tmax'],
                'prcp': weather['precipitation'],
                'eto': weather['eto']
            })
    
    # Write this data to the database
    write_to_database(db_path, formatted_data)
    
def get_forecast_data(start_date=None, end_date=None, base_dir=None):
    """
    Retrieve weather data from database, optionally filtered by date range
    Returns data sorted by datetime
    """
    db_path = get_database_path(base_dir)

    if not os.path.exists(db_path):
        print("Database does not exist")
        return []
    
    retrived_data = get_from_database(start_date, end_date, db_path)

    return retrived_data

if __name__ == '__main__':
    write_forecast_data()