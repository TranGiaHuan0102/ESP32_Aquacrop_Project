import os
from aquacrop import AquaCropModel, Soil, Crop, InitialWaterContent
from aquacrop.utils import prepare_weather
from datetime import datetime, timedelta
from weather import get_climate_data_path

def run_simulation(base_dir=get_climate_data_path(), days_ahead=6):
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
    run_simulation()

if __name__ == '__main__':
    main()