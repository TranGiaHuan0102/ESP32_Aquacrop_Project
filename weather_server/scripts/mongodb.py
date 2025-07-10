import os

from datetime import datetime
from pymongo import MongoClient
from paths import get_server_root
from dotenv import load_dotenv

# OpenWeatherMap config
if os.getenv("GITHUB_ACTIONS") != "true":
    server_root = get_server_root()    
    load_dotenv(dotenv_path=server_root / 'env/mongodb.env')

MONGODB_URI = os.getenv("MONGODB_URI")

def get_db():
    client = MongoClient(MONGODB_URI)
    
    db = client.weather_irrigation

    return db.weather_data

def write_database(weather_data):
    collection = get_db()
    
    for item in weather_data:
        collection.replace_one(
            {"date": item["datetime"]},         # Find doc with this date
            {
                "timestamp": datetime.now(),
                "date": item["datetime"],
                "weather": item
            },
            upsert=True                         # Insert if doesn't exist, replace if exists
        )

def get_database(start_date, end_date):
    collection = get_db()
    
    return list(collection.find(
        {"date": {"$gte": start_date.date().isoformat(), "$lte": end_date.date().isoformat()}}
    ))