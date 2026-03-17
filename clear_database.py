#!/usr/bin/env python3
"""
Script to delete all records from the SQLite database.
Usage: python clear_database.py
"""

import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from job_app_helper.config import load_settings


def clear_applications():
    """Delete all records from the applications table and reset autoincrement."""
    
    # Load settings to get database path
    settings = load_settings()
    db_path = settings.storage.sqlite_db_path
    
    # Check if database file exists
    if not Path(db_path).exists():
        print(f"Database file not found: {db_path}")
        print("Nothing to delete.")
        return False
    
    try:
        # Connect to database and delete all records
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='applications'"
        )
        if not cursor.fetchone():
            print("Table 'applications' does not exist.")
            print("Nothing to delete.")
            conn.close()
            return False
        
        # Get current record count
        cursor.execute("SELECT COUNT(*) FROM applications")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("Table 'applications' is already empty.")
            print("Nothing to delete.")
            conn.close()
            return True
        
        print(f"Found {count} record(s) in the database.")
        
        # Delete all records from applications table
        cursor.execute("DELETE FROM applications")
        print("Deleted all records from 'applications' table.")
        
        # Reset autoincrement
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'applications'")
        print("Reset autoincrement counter.")
        
        # Commit changes
        conn.commit()
        print("Changes committed successfully.")
        
        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM applications")
        remaining = cursor.fetchone()[0]
        print(f"Remaining records: {remaining}")
        
        conn.close()
        
        if remaining == 0:
            print("\n[OK] Database cleared successfully!")
            return True
        else:
            print("\n[WARN] Some records may remain.")
            return False
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    success = clear_applications()
    sys.exit(0 if success else 1)
