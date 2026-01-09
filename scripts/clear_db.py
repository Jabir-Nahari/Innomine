"""Database Cleanup Utility.

DANGER: This script deletes ALL data from the Innomine sensor and alarm tables.
Use with caution.

Usage:
    python scripts/clear_db.py
"""

import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from db_interfaces.db import get_connection

def clear_all_tables():
    tables = [
        "alarms",
        "scd40_data",
        "ds18b20_data",
        "mpu6050_data"
    ]
    
    print("⚠️  WARNING: This will DELETE ALL DATA from the following tables:")
    for t in tables:
        print(f"  - {t}")
    
    confirm = input("\nType 'yes' to proceed: ")
    if confirm.lower() != "yes":
        print("Aborted.")
        return

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for table in tables:
                    print(f"Truncating {table}...")
                    # CASCADE is used to clear any dependent rows if foreign keys existed,
                    # though in this schema they are mostly independent.
                    cur.execute(f"TRUNCATE TABLE {table} RESTRICT;")
            conn.commit()
        print("\n✅ All tables cleared successfully.")
        
    except Exception as e:
        print(f"\n❌ Error clearing tables: {e}")

if __name__ == "__main__":
    clear_all_tables()
