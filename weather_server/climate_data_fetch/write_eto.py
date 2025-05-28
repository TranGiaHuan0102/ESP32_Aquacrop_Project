import requests
import datetime
import math

from weather import fetch_weather_data
from climateData_writer import data_writer

def calculate_eto_penman_monteith(tmax, tmin, rh, wind_speed, solar_radiation, elevation=0):
    """
    Calculate reference evapotranspiration using simplified Penman-Monteith equation
    
    Parameters:
    - tmax: Maximum temperature (°C)
    - tmin: Minimum temperature (°C)
    - rh: Relative humidity (%)
    - wind_speed: Wind speed at 2m (m/s)
    - solar_radiation: Solar radiation (MJ/m²/day)
    - elevation: Elevation above sea level (m)
    """
    
    # Mean temperature
    tmean = (tmax + tmin) / 2
    
    # Atmospheric pressure (kPa)
    P = 101.3 * ((293 - 0.0065 * elevation) / 293) ** 5.26
    
    # Psychrometric constant (kPa/°C)
    gamma = 0.665 * P
    
    # Saturation vapor pressure (kPa)
    es_tmax = 0.6108 * math.exp(17.27 * tmax / (tmax + 237.3))
    es_tmin = 0.6108 * math.exp(17.27 * tmin / (tmin + 237.3))
    es = (es_tmax + es_tmin) / 2
    
    # Actual vapor pressure (kPa)
    ea = es * rh / 100
    
    # Slope of saturation vapor pressure curve (kPa/°C)
    delta = 4098 * (0.6108 * math.exp(17.27 * tmean / (tmean + 237.3))) / ((tmean + 237.3) ** 2)
    
    # Net radiation (MJ/m²/day) - simplified approach
    # Convert solar radiation to net radiation (approximate)
    Rn = solar_radiation * 0.77 - 2.45  # Simplified net radiation estimation
    
    # Soil heat flux (assumed to be 0 for daily calculations)
    G = 0
    
    # Reference evapotranspiration (mm/day)
    numerator = 0.408 * delta * (Rn - G) + gamma * 900 / (tmean + 273) * wind_speed * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * wind_speed)
    
    eto = numerator / denominator
    
    return max(0, eto)  # ET₀ cannot be negative

def fetch_and_calculate_eto(lat, lon, elevation=0):
    # Get weather data from the NASA POWER API
    weather_data = fetch_weather_data(lat, lon)

    if not weather_data:
        return None

    eto_results = {}

    # Get the dates from any parameter 
    dates = list(weather_data.get('T2M_MAX', {}).keys())

    for date in dates:
        try:
            tmax = weather_data['T2M_MAX'][date]
            tmin = weather_data['T2M_MIN'][date]
            rh = weather_data['RH2M'][date]
            wind_speed = weather_data['WS2M'][date]
            solar_radiation = weather_data['ALLSKY_SFC_SW_DWN'][date]
            
            # Check for missing data
            if any(val == -999 or val is None for val in [tmax, tmin, rh, wind_speed, solar_radiation]):
                continue
            
            eto = calculate_eto_penman_monteith(tmax, tmin, rh, wind_speed, solar_radiation, elevation)
            eto_results[date] = [round(eto, 2)]
            
        except KeyError as e:
            print(f"Missing parameter for {date}: {e}")
        except Exception as e:
            print(f"Error calculating ET₀ for {date}: {e}")

    
    eto_values = list(value for value in eto_results.values())

    return dates, eto_values

# Binh Duong coordinates
def eto_writer(latitude=10.8231, longitude=106.6297, elevation=19):
    dates, eto_values = fetch_and_calculate_eto(latitude, longitude, elevation)
    data_writer("BinhDuong.eto", dates, eto_values)

def main():
    eto_writer()
if __name__ == '__main__':
    main()

