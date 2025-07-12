from pathlib import Path

def get_server_root():
    # Get the directory where this script is located
    return Path(__file__).resolve().parent.parent