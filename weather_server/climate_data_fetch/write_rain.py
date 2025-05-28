import requests
import datetime

from weather import fetch_weather_data
from climateData_writer import data_writer


def fetch_precipitation(lat, lon, elevation=0):
    # Get weather data from the NASA POWER API
    weather_data = fetch_weather_data(lat, lon)

    if not weather_data:
        return None
    
    precipitation_results = {}

    # Get the dates from any parameter 
    dates = list(weather_data.get('PRECTOTCORR', {}).keys())

    for date in dates:
        try:
            rain = weather_data["PRECTOTCORR"][date]

            # Check for missing data
            if (rain == -999 or rain is None):
                continue

            precipitation_results[date] = [round(rain, 2)]

        except KeyError as e:
            print(f"Missing parameter for {date}: {e}")
        except Exception as e:
            print(f"Error fetching PRECTOTCORR for {date}: {e}")

    precipitation_values = list(value for value in precipitation_results.values())

    return dates, precipitation_values

def precipitation_writer(latitude=10.8231, longitude=106.6297, elevation=19):
    dates, precipitation_values = fetch_precipitation(latitude, longitude, elevation)

    data_writer("BinhDuong.PLU", dates, precipitation_values)

def main():
    precipitation_writer()

if __name__ == '__main__':
    main()