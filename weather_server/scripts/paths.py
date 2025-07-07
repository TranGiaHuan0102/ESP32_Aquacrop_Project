from pathlib import Path

def get_server_root():
    # Get the directory where this script is located
    return Path(__file__).resolve().parent.parent

def get_climate_data_path():
    # Get the database directory
    return str(get_server_root() / "climate_data")