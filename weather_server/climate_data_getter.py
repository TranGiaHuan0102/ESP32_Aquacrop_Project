import requests
import math
import datetime
import os

def fetch_weather_data(lat, lon, days_back, duration):
    # Early exit if invalid days_back
    if (days_back <= 0 or duration <= 0):
        print("INVALID PARAM INPUT, MUST BE POSITIVE")
        return None

    """Fetch weather data from NASA POWER API"""
    today = datetime.date.today()

    # Start_date is 67 days ago, fetch data for 2 months, by default
    start_date = today - datetime.timedelta(days=days_back)
    end_date = today
        
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
    
def calculate_eto_penman_monteith(tmax, tmin, rh, wind_speed, solar_radiation, elevation):
    """
    Calculate reference evapotranspiration using simplified Penman-Monteith equation
    
    Parameters:
    - tmax: Maximum temperature (°C)
    - tmin: Minimum temperature (°C)
    - rh: Relative humidity (%)
    - wind_speed: Wind speed at 2m (m/s)
    - solar_radiation: Solar radiation (MJ/m²/day)
    - elevation: Elevation above sea level, 12 for Binh Duong (m)
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

def compile_data(latitude=10.8231, longitude=106.6297, elevation=12, days_back=365, duration=365):
    # Get weather data from the NASA POWER API
    weather_data = fetch_weather_data(latitude, longitude, days_back, duration)

    if not weather_data:
        return None
    
    climate_data = []

    # Get the dates from any parameter 
    dates = list(weather_data.get('T2M_MAX', {}).keys())

    for date in dates:
        try:
            # Extract data
            tmin = weather_data["T2M_MIN"][date]
            tmax = weather_data["T2M_MAX"][date]
            rh = weather_data['RH2M'][date]
            wind_speed = weather_data['WS2M'][date]
            solar_radiation = weather_data['ALLSKY_SFC_SW_DWN'][date]
            rain = weather_data["PRECTOTCORR"][date]

            # Check for missing data
            if any(val == -999 or val is None for val in [tmax, tmin, rh, wind_speed, solar_radiation, rain]):
                continue

            eto = calculate_eto_penman_monteith(tmax, tmin, rh, wind_speed, solar_radiation, elevation)

            result = {
                "day"  : int(date[6:]),
                "month" : int(date[4:6]),
                "year" : int(date[0:4]),
                "tmax" : round(tmax, 2),
                "tmin" : round(tmin, 2),
                "rain" : round(rain, 2),
                "eto"  : round(eto, 2)
            }

            climate_data.append(result)

        except KeyError as e:
            print(f"Missing parameter for {date}: {e}")
        except Exception as e:
            print(f"Error fetching T2M_MAX for {date}: {e}")

    return climate_data

def data_writer(filepath, data):
    # Create directory if missing
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    last_date = None

    if os.path.exists(filepath):
        with open(filepath, 'r+') as f:
            lines = f.readlines()

            # Find last written date (skip header)
            if len(lines) > 1:
                # Last non-empty line
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            try:
                                day, month, year = map(int, parts[:3])
                                last_date = (year, month, day)
                                break
                            except ValueError:
                                pass

            # Clean trailing empty lines
            while lines and lines[-1].strip() == "":
                lines.pop()

            # Rewrite cleaned file if modified
            f.seek(0)
            f.writelines(lines)
            f.truncate()

    else:
        # Create new file with header
        with open(filepath, 'w') as f:
            f.write("Day\tMonth\tYear\tTmin(C)\tTmax(C)\tPrcp(mm)\tEt0(mm)\n")

    # Append only new data entries with date > last_date
    with open(filepath, 'a') as f:
        for entry in data:
            # Construct date tuple for comparison
            entry_date = (entry["year"], entry["month"], entry["day"])

            # Write if new date (or if no last_date yet)
            if last_date is None or entry_date > last_date:
                f.write(
                    f'{entry["day"]}\t{entry["month"]}\t{entry["year"]}\t'
                    f'{entry["tmin"]}\t{entry["tmax"]}\t{entry["rain"]}\t{entry["eto"]}\n'
                )

