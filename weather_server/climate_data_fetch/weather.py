import requests
import datetime

def fetch_weather_data(lat, lon, days_back=67, duration=60):
    
    # Early exit if invalid days_back
    if (days_back < 60):
        print("Earlist to fetch data is 2 months ago!")
        return None


    """Fetch weather data from NASA POWER API"""
    today = datetime.date.today()

    # Start_date is 67 days ago, fetch data for 2 months, by default
    start_date = today - datetime.timedelta(days=days_back)
    end_date = start_date +  datetime.timedelta(days=(duration))
        
    base_url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    
    # Parameters needed for ET₀ calculation
    params = {
        "parameters": "T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON"
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if 'properties' in data and 'parameter' in data['properties']:
        return data['properties']['parameter']
    else:
        print("Error fetching data:", data)
        return None

def get_co2_concentration(year):
    """
    Get atmospheric CO2 concentration for a given year
    Based on Mauna Loa observatory data and projections
    """
    # Historical and projected CO2 concentrations (ppm)
    co2_data = {
        2020: 414.2,
        2021: 416.4,
        2022: 420.0,
        2023: 421.1,
        2024: 423.0,
        2025: 425.0,  # Projected
        2026: 427.0,  # Projected
    }
    
    return co2_data.get(year, 425.0)  # Default to 2025 value

def main():
    ...

if __name__ == '__main__':
    main()