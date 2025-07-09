import os
from aquacrop import AquaCropModel, Soil, Crop, InitialWaterContent
from aquacrop.utils import prepare_weather
from datetime import datetime, timedelta
from paths import get_climate_data_path
from database import get_from_database

def run_simulation(base_dir=get_climate_data_path(), days_ahead=4):
    """
    Find the next 5 days of weather data and run AquaCrop simulation
    Handles edge cases where data may span across multiple files
    """
    try:
        # Get current date (tomorrow since forecasts start from tomorrow)
        start_date = datetime.now() - timedelta(days=1)
        target_date = start_date + timedelta(days=days_ahead)
        
        # Get all weather files sorted by date
        weather_files = get_from_database(start_date=start_date, end_date=target_date)
        
        # Check if we have enough data
        if len(weather_files) < days_ahead:
            print(f"Warning: Only found {len(weather_files)} days of data, need {days_ahead}")
            if len(weather_files) == 0:
                print("No data found for the target dates")
                return None

        # Create temporary weather file for AquaCrop
        temp_weather_file = os.path.join(base_dir, "temp_aquacrop_weather.txt")

        with open(temp_weather_file, 'w') as f:
            # Write header
            f.write("Day\tMonth\tYear\tTmin(C)\tTmax(C)\tPrcp(mm)\tEt0(mm)\n")
            
             # Write data rows
            for data in weather_files:
                f.write(f"{data['day']}\t{data['month']}\t{data['year']}\t{data['tmin']}\t{data['tmax']}\t{data['prcp']}\t{data['eto']}\n")
        
        # Run aquacrop simulation on weather file
        simulation_table = aquacrop_simulation(temp_weather_file)

        # Determine whether to water today or not
        irrigation_today = irrigation_decision(simulation_table)

        print(irrigation_today)

        return irrigation_today

    except Exception as e:
        print(f"Error in aquacrop_process: {e}")
        return None
    
    finally:
        # Always try to remove temp file if it was created
        if temp_weather_file and os.path.exists(temp_weather_file):
            try:
                os.remove(temp_weather_file)
            except Exception as e:
                print(f"Warning: Could not remove temp file {temp_weather_file}: {e}")

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
    planting_date = start_day.strftime(start_day.strftime("%m/%d"))
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
    return water_flux_results

def irrigation_decision(simulation_table, growth_stage=None):
    # Thresholds for maize (adjust based on soil type)
    if growth_stage == "flowering":
        critical_wr = 50 
    elif growth_stage == "vegetative":
        critical_wr = 40
    else:
        critical_wr = 45
    
    # Decision logic
    WR_day5 = simulation_table["Wr"].iloc[-1]
    if WR_day5 < critical_wr:
        return True
    else:
        return False
       
def main():
    run_simulation()

if __name__ == '__main__':
    main()