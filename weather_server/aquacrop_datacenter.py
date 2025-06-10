import os
import requests
import pandas as pd
import math


from aquacrop import AquaCropModel, Soil, Crop, InitialWaterContent
from aquacrop.utils import prepare_weather
from climate_data_getter import compile_data, data_writer
from datetime import datetime, timedelta

# --- Constants and file paths ---
NASA_FILEPATH = "climate_data\\binhduong_climate_nasa.txt"

# --- Load NASA data ---
def load_nasa_data():
    # Assume compile_data() can accept start/end date or days_back/duration parameters
    # raw_data = compile_data(days_back=21, duration=300)

    # data_writer(NASA_FILEPATH, raw_data)
    
    # Prepare weather data (expects NASA_FILEPATH data)
    return prepare_weather(NASA_FILEPATH)


# Load NASA data (14 to 7 days ago)
nasa_weather_df = load_nasa_data()

# Define Soil type
sandy_loam = Soil(soil_type='SandyLoam')

# Define InitWC value
InitWC = InitialWaterContent(value=['FC'])

start_day = nasa_weather_df["Date"].iloc[0]
final_day = nasa_weather_df["Date"].iloc[-1]

# Planting date
planting_date = start_day.strftime("%m/%d")
wheat = Crop('Wheat', planting_date=planting_date)

# Combine into aquacrop model and specify start and end simulation date
sim_start_date = start_day.strftime("%Y/%m/%d")
sim_end_date = final_day.strftime("%Y/%m/%d")

model = AquaCropModel(sim_start_time=sim_start_date,
                      sim_end_time=sim_end_date,
                      weather_df=nasa_weather_df,
                      soil=sandy_loam,
                      crop=wheat,
                      initial_water_content=InitWC)

# run model till termination
model.run_model(till_termination=True)

print(model._outputs.water_flux[model._outputs.water_flux["dap"] != 0].tail(10))