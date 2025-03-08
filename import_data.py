from sqlalchemy import create_engine
import pandas as pd
import subprocess
import os

# Database connection parameters
DB_NAME = "sensordata"
DB_USER = "admin"
DB_PASSWORD = "admin"
DB_HOST = "localhost"  # Change if running on another machine
DB_PORT = "5432"

# Path to the SQL dump file
SQL_DUMP_PATH = "grafana/data/Export_Processed_PolluscopeDB.sql"

# Connect to PostgreSQL
engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def restore_database():
    """Restore the database from the SQL dump file if needed."""
    print("🔄 Restoring database from SQL dump...")
    try:
        subprocess.run(
            f'psql -U {DB_USER} -d {DB_NAME} -h {DB_HOST} -p {DB_PORT} -f "{SQL_DUMP_PATH}"',
            shell=True,
            check=True,
        )
        print("✅ Database restored successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error restoring database: {e}")
        exit(1)

def fetch_data(query):
    """Execute a SQL query and return the results as a DataFrame."""
    return pd.read_sql(query, engine)

# Check if SQL dump exists before restoring
if os.path.exists(SQL_DUMP_PATH):
    restore_database()
else:
    print(f"⚠️ SQL dump file not found at {SQL_DUMP_PATH}. Skipping restoration.")

# Fetch full datasets
query_pollution = """
SELECT time, participant_virtual_id, "Temperature", "Humidity", "NO2", "BC", "PM1.0", "PM2.5", "PM10", "Speed", activity 
FROM public.data_processed_vgp
ORDER BY time;
"""

query_gps = """
SELECT time, participant_virtual_id, lat, lon 
FROM public.clean_gps
ORDER BY time;
"""

if __name__ == "__main__":
    # Load pollution data
    df_pollution = fetch_data(query_pollution)
    print("📊 Pollution Data Sample:")
    print(df_pollution.head())

    # Load GPS data
    df_gps = fetch_data(query_gps)
    print("\n📍 GPS Data Sample:")
    print(df_gps.head())

    # 🔍 Fix Data Issues
    print("\n🔧 Fixing Data Issues...")

    # Convert `participant_virtual_id` to integer
    df_pollution["participant_virtual_id"] = pd.to_numeric(df_pollution["participant_virtual_id"], errors="coerce").astype("Int64")
    df_gps["participant_virtual_id"] = pd.to_numeric(df_gps["participant_virtual_id"], errors="coerce").astype("Int64")

    # Fill missing values
    df_pollution["Speed"].fillna(0, inplace=True)  # Missing speed → Assume stationary
    df_pollution["activity"].fillna("Unknown", inplace=True)  # Missing activity → "Unknown"

    # Forward-fill missing sensor values (assumes previous values are relevant)
    df_pollution.fillna(method="ffill", inplace=True)

    # Align timestamps: Keep only overlapping timestamps
    common_timestamps = set(df_pollution["time"]).intersection(set(df_gps["time"]))
    df_pollution = df_pollution[df_pollution["time"].isin(common_timestamps)]
    df_gps = df_gps[df_gps["time"].isin(common_timestamps)]

    print("\n✅ Data Cleaning Complete!")

    # Export cleaned data for verification
    df_pollution.to_csv("clean_pollution_data.csv", index=False)
    df_gps.to_csv("clean_gps_data.csv", index=False)

    print("\n📂 Cleaned data exported to CSV.")

    # Save cleaned data back to PostgreSQL
    print("\n🛠️ Updating PostgreSQL database...")
    df_pollution.to_sql("data_processed_vgp_cleaned", engine, if_exists="replace", index=False)
    df_gps.to_sql("clean_gps_cleaned", engine, if_exists="replace", index=False)

    print("\n✅ Database updated with cleaned data!")
