"""
POKE Stats Microservice
Obtiene las estadísticas de Pokemon desde PostgreSQL
Conectado solo con la base de datos (como se muestra en el diagrama)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import time
import httpx
import logging
import sys

# Configurar logging
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

app = FastAPI(title="POKE Stats Service", version="1.0.0")

# Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'monitormach_pass_2026')
DB_NAME = os.getenv('DB_NAME', 'monitormach_db')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
LOGGING_SERVICE_URL = os.getenv('LOGGING_SERVICE_URL', 'http://localhost:8004')


# ==================== Models ====================
class PokemonStats(BaseModel):
    """Estadísticas de un Pokemon"""
    name: str
    hp: int
    attack: int
    defense: int
    sp_atk: int
    sp_def: int
    speed: int


class StatsResponse(BaseModel):
    """Respuesta con estadísticas"""
    success: bool
    data: Optional[PokemonStats] = None
    message: str


# ==================== Database Connection ====================
def get_db_connection():
    """Obtiene una conexión a PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise


# ==================== Logging Helper ====================
async def send_log(api: str, function: str, message: str, level: str = "INFO", latency_ms: float = None):
    """Envía un log al servicio centralizado"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "module": "POKE_STATS",
                "api": api,
                "function": function,
                "message": message,
                "level": level,
                "latency_ms": latency_ms
            }
            response = await client.post(f"{LOGGING_SERVICE_URL}/logs", json=payload, timeout=5.0)

            if response.status_code == 200:
                logger.info(f"Log sent successfully: {api}.{function}")
            else:
                logger.warning(f"Log send failed with status {response.status_code}: {api}.{function}")

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to logging service at {LOGGING_SERVICE_URL}: {e}")
    except httpx.TimeoutException as e:
        logger.error(f"Timeout sending log to logging service: {e}")
    except Exception as e:
        logger.error(f"Unexpected error sending log: {e}", exc_info=True)


# ==================== Endpoints ====================
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()

        return {
            "status": "healthy",
            "service": "poke_stats",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "poke_stats",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "database": "disconnected",
            "error": str(e)
        }


@app.get("/stats/{pokemon_name}", response_model=StatsResponse, tags=["Stats"])
async def get_pokemon_stats(pokemon_name: str):
    """
    Obtiene las estadísticas de un Pokemon por nombre

    Columnas retornadas: HP, Attack, Defense, Sp.Atk, Sp.Def, Speed

    Ejemplo: GET /stats/pikachu
    """
    start_time = time.time()

    try:
        # Normalizar nombre (convertir a título)
        normalized_name = pokemon_name.strip().lower()

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Buscar Pokemon (case-insensitive)
        cursor.execute(
            """
            SELECT name, hp, attack, defense, sp_atk, sp_def, speed
            FROM pokemon_stats
            WHERE LOWER(name) = %s
            """,
            (normalized_name,)
        )

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        latency_ms = (time.time() - start_time) * 1000

        if result:
            stats = PokemonStats(**result)

            # Enviar log
            await send_log(
                api="GET_STATS",
                function="get_pokemon_stats",
                message=f"Pokemon encontrado: {result['name']}",
                level="INFO",
                latency_ms=latency_ms
            )

            return StatsResponse(
                success=True,
                data=stats,
                message="Stats retrieved successfully"
            )
        else:
            # Enviar log de error
            await send_log(
                api="GET_STATS",
                function="get_pokemon_stats",
                message=f"Pokemon no encontrado: {pokemon_name}",
                level="WARNING",
                latency_ms=latency_ms
            )

            raise HTTPException(
                status_code=404,
                detail=f"Pokemon '{pokemon_name}' not found"
            )

    except psycopg2.Error as e:
        latency_ms = (time.time() - start_time) * 1000
        await send_log(
            api="GET_STATS",
            function="get_pokemon_stats",
            message=f"Database error: {str(e)}",
            level="ERROR",
            latency_ms=latency_ms
        )
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        await send_log(
            api="GET_STATS",
            function="get_pokemon_stats",
            message=f"Unexpected error: {str(e)}",
            level="ERROR",
            latency_ms=latency_ms
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", response_model=dict, tags=["Stats"])
async def list_all_stats(limit: int = 10):
    """
    Lista los primeros N Pokemon con sus estadísticas (útil para testing)

    Parámetros:
    - limit: cantidad de Pokemon a retornar (default: 10, max: 100)

    Ejemplo: GET /stats?limit=20
    """
    try:
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 1

        start_time = time.time()

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT name, hp, attack, defense, sp_atk, sp_def, speed
            FROM pokemon_stats
            LIMIT %s
            """,
            (limit,)
        )

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        latency_ms = (time.time() - start_time) * 1000

        stats_list = [PokemonStats(**row) for row in results]

        await send_log(
            api="GET_STATS_LIST",
            function="list_all_stats",
            message=f"Retrieved {len(stats_list)} Pokemon stats",
            level="INFO",
            latency_ms=latency_ms
        )

        return {
            "success": True,
            "count": len(stats_list),
            "data": stats_list
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
