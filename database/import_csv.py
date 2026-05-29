#!/usr/bin/env python3
"""
Script para importar datos del CSV de Pokemon a PostgreSQL
Uso: python database/import_csv.py
"""

import csv
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'monitormach_pass_2026')
DB_NAME = os.getenv('DB_NAME', 'monitormach_db')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

CSV_PATH = 'Pokemon.csv'

def import_pokemon_data():
    """Import Pokemon data from CSV to PostgreSQL"""

    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        cursor = conn.cursor()

        print(f"✓ Connected to PostgreSQL: {DB_HOST}:{DB_PORT}")

        # Read CSV
        data = []
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Extract only required columns
                name = row['Name'].strip()
                hp = int(row['HP'].strip())
                attack = int(row['Attack'].strip())
                defense = int(row['Defense'].strip())
                sp_atk = int(row['Sp. Atk'].strip())
                sp_def = int(row['Sp. Def'].strip())
                speed = int(row['Speed'].strip())

                data.append((name, hp, attack, defense, sp_atk, sp_def, speed))

        print(f"✓ Read {len(data)} Pokemon from CSV")

        # Insert data
        query = """
        INSERT INTO pokemon_stats (name, hp, attack, defense, sp_atk, sp_def, speed)
        VALUES %s
        ON CONFLICT (name) DO NOTHING
        """

        execute_values(cursor, query, data)
        conn.commit()

        # Verify
        cursor.execute("SELECT COUNT(*) FROM pokemon_stats")
        count = cursor.fetchone()[0]

        print(f"✓ Imported {count} unique Pokemon to database")

        cursor.close()
        conn.close()

        print("✓ Import completed successfully!")

    except Exception as e:
        print(f"✗ Error: {e}")
        raise

if __name__ == '__main__':
    import_pokemon_data()
