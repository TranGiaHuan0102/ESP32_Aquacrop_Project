import requests
import datetime

from weather import fetch_weather_data
from climateData_writer import data_writer

def fetch_temperature(lat, lon, elevation=0):
    # Get weather data from the NASA POWER API
    weather_data = fetch_weather_data(lat, lon)

    if not weather_data:
        return None
    
    temperature_results = {}

    # Get the dates from any parameter 
    dates = list(weather_data.get('T2M_MAX', {}).keys())

    for date in dates:
        try:
            tmin = weather_data["T2M_MIN"][date]
            tmax = weather_data["T2M_MAX"][date]
            
            # Check for missing data
            if any(val == -999 or val is None for val in [tmin, tmax]):
                continue

            temperature_results[date] = [round(tmin, 2), round(tmax, 2)]

        except KeyError as e:
            print(f"Missing parameter for {date}: {e}")
        except Exception as e:
            print(f"Error fetching T2M_MAX for {date}: {e}")

    temperature_values = list(value for value in temperature_results.values())

    return dates, temperature_values

def temperature_writer(latitude=10.8231, longitude=106.6297, elevation=19):
    dates, temperature_values = fetch_temperature(latitude, longitude, elevation)

    data_writer("BinhDuong.Tnx", dates, temperature_values)

def main():
    temperature_writer()

if __name__ == '__main__':
    main()