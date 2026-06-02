#!/usr/bin/env python3
"""
Script para importar datos del CSV de Pokemon a PostgreSQL
Uso: python database/import_csv.py
"""

import csv
import psycopg2
from psycopg2.extras import execute_values
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'monitormach_pass_2026')
DB_NAME = os.getenv('DB_NAME', 'monitormach_db')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

# import_csv.py está en: /app/import_csv.py (dentro del contenedor)
# Pokemon.csv está en: /app/database/Pokemon.csv
SCRIPT_DIR = Path(__file__).parent  # /app
CSV_PATH = SCRIPT_DIR / 'database/Pokemon.csv'


def import_pokemon_data():
    """Import Pokemon data from CSV to PostgreSQL"""

    try:
        # Verificar que el CSV existe
        if not CSV_PATH.exists():
            print(f"✗ Error: CSV file not found at {CSV_PATH}")
            print(f"  Current directory: {Path.cwd()}")
            print(f"  Looking for: {CSV_PATH.absolute()}")
            sys.exit(1)

        print(f"✓ Found CSV at: {CSV_PATH.absolute()}")

        # Connect to PostgreSQL
        print(f"Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        cursor = conn.cursor()

        print(f"✓ Connected to PostgreSQL: {DB_HOST}:{DB_PORT}")
        print(f"✓ Database: {DB_NAME}")

        # Check existing data
        cursor.execute("SELECT COUNT(*) FROM pokemon_stats")
        existing_count = cursor.fetchone()[0]
        print(f"  Current records in DB: {existing_count}")

        # Read CSV
        print("\nReading CSV file...")
        data = []
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, 1):
                try:
                    # Extract and normalize columns
                    # IMPORTANTE: Convertir nombre a minúsculas para coincidencia con búsquedas
                    name = row['Name'].strip().lower()  # ← NORMALIZADO A MINÚSCULAS
                    hp = int(row['HP'].strip())
                    attack = int(row['Attack'].strip())
                    defense = int(row['Defense'].strip())
                    sp_atk = int(row['Sp. Atk'].strip())
                    sp_def = int(row['Sp. Def'].strip())
                    speed = int(row['Speed'].strip())

                    data.append((name, hp, attack, defense, sp_atk, sp_def, speed))

                except (ValueError, KeyError) as e:
                    print(f"  ✗ Error parsing row {row_num}: {e}")
                    continue

        print(f"✓ Read {len(data)} Pokemon from CSV")

        if len(data) == 0:
            print("✗ No data was read from CSV!")
            sys.exit(1)

        # Insert data
        print("\nInserting into database...")
        query = """
        INSERT INTO pokemon_stats (name, hp, attack, defense, sp_atk, sp_def, speed)
        VALUES %s
        ON CONFLICT (name) DO NOTHING
        """

        execute_values(cursor, query, data)
        conn.commit()

        # Verify import
        cursor.execute("SELECT COUNT(*) FROM pokemon_stats")
        total_count = cursor.fetchone()[0]
        new_count = total_count - existing_count

        print(f"✓ Imported {new_count} new Pokemon to database")
        print(f"✓ Total records in DB: {total_count}")

        # Show some samples
        print("\nSample data from database:")
        cursor.execute("""
            SELECT name, hp, attack, defense, sp_atk, sp_def, speed
            FROM pokemon_stats
            LIMIT 5
        """)
        for name, hp, atk, df, sp_atk, sp_def, spd in cursor.fetchall():
            print(f"  - {name}: HP={hp}, ATK={atk}, DEF={df}, SPATK={sp_atk}, SPDEF={sp_def}, SPD={spd}")

        # Check specific pokemon
        cursor.execute(
            "SELECT hp, attack, defense, sp_atk, sp_def, speed FROM pokemon_stats WHERE name = %s",
            ('pikachu',)
        )
        result = cursor.fetchone()
        if result:
            print(f"\n✓ 'pikachu' found in database!")
            hp, atk, df, sp_atk, sp_def, spd = result
            print(f"  Stats: HP={hp}, ATK={atk}, DEF={df}, SPATK={sp_atk}, SPDEF={sp_def}, SPD={spd}")
        else:
            print(f"\n✗ 'pikachu' NOT found in database!")

        cursor.close()
        conn.close()

        print("\n✓ Import completed successfully!")
        return True

    except psycopg2.Error as e:
        print(f"✗ Database Error: {e}")
        print(f"  Check that PostgreSQL is running and accessible")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    import_pokemon_data()
