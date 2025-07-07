import sqlite3
import os
from paths import get_climate_data_path

def get_database_path(base_dir=None):
    """Get the path to the weather database"""
    if base_dir is None:
        base_dir = get_climate_data_path()  # Your existing function
    
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, 'weather_data.db')

def initialize_database(db_path):
    """Initialize the weather database with required table and indexes"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table with all required columns including datetime
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            datetime TEXT NOT NULL UNIQUE,
            tmin REAL NOT NULL,
            tmax REAL NOT NULL,
            prcp REAL NOT NULL,
            eto REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create index on datetime column for efficient searching and sorting
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_datetime ON weather_data(datetime)
    ''')

    conn.commit()
    conn.close()

def write_to_database(db_path, formatted_data):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Process each entry
    updated_count = 0
    inserted_count = 0

    for data in formatted_data:
        # First check if the date exists
        cursor.execute('SELECT id FROM weather_data WHERE datetime = ?', (data['datetime'],))
        existing_row = cursor.fetchone()
        
        if existing_row:
            # Update existing entry
            cursor.execute('''
                UPDATE weather_data 
                SET day = ?, month = ?, year = ?, tmin = ?, tmax = ?, prcp = ?, eto = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE datetime = ?
            ''', (data['day'], data['month'], data['year'], data['tmin'], 
                  data['tmax'], data['prcp'], data['eto'], data['datetime']))
            
            updated_count += 1
            print(f"Updated existing entry for {data['datetime']}")
        else:
            # Insert new entry
            cursor.execute('''
                INSERT INTO weather_data (day, month, year, datetime, tmin, tmax, prcp, eto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['day'], data['month'], data['year'], data['datetime'],
                  data['tmin'], data['tmax'], data['prcp'], data['eto']))
            
            inserted_count += 1
            print(f"Inserted new entry for {data['datetime']}")

    conn.commit()
    conn.close()

    print(f"Database operation completed: {inserted_count} inserted, {updated_count} updated")
    return True

def get_from_database(start_date, end_date, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if start_date:
        # Just filter by start_date - ignore end_date if it exceeds available data
        cursor.execute('''
            SELECT day, month, year, datetime, tmin, tmax, prcp, eto, created_at, updated_at
            FROM weather_data 
            WHERE datetime >= ?
            ORDER BY datetime
        ''', (start_date,))
    else:
        cursor.execute('''
            SELECT day, month, year, datetime, tmin, tmax, prcp, eto, created_at, updated_at
            FROM weather_data 
            ORDER BY datetime
        ''')
    rows = cursor.fetchall()
    conn.close()

    # Convert to list of dictionaries for easier handling
    columns = ['day', 'month', 'year', 'datetime', 'tmin', 'tmax', 'prcp', 'eto', 'created_at', 'updated_at']
    return [dict(zip(columns, row)) for row in rows]

