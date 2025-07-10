import os
from aquacrop import AquaCropModel, Soil, Crop, InitialWaterContent
from aquacrop.utils import prepare_weather
from datetime import datetime, timedelta
from mongodb import get_database

def run_simulation(days_ahead=4):
    """
    Find the next 5 days of weather data and run AquaCrop simulation
    Handles edge cases where data may span across multiple files
    """
    try:
        start_date = datetime.now()
        target_date = start_date + timedelta(days=days_ahead)
        weather_documents = get_database(start_date, target_date)
        temp_weather_file = create_aquacrop_weather_file(weather_documents)
        
        try:
            result = aquacrop_simulation(temp_weather_file)
            irrigation_today =  irrigation_decision(result)     # Boolean value
            return irrigation_today
        finally:
            os.remove(temp_weather_file)

    except Exception as e:
        print(f"Error retrieving data from MongoDB: {e}")
        return None

def create_aquacrop_weather_file(weather_documents):
    # Create temporary weather file for AquaCrop
    temp_weather_file = "temp_aquacrop_weather.txt"

    with open(temp_weather_file, 'w') as f:
        # Write header
        f.write("Day\tMonth\tYear\tTmin(C)\tTmax(C)\tPrcp(mm)\tEt0(mm)\n")
        
            # Write data rows
        for docu in weather_documents:
            data = docu["weather"]
            f.write(f"{data['day']}\t{data['month']}\t{data['year']}\t{data['tmin']}\t{data['tmax']}\t{data['prcp']}\t{data['eto']}\n")

    return temp_weather_file

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

