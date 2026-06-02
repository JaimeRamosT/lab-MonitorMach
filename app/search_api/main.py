"""
Search API Service (Orquestador)
Coordina búsquedas entre los tres microservicios POKE
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List  # noqa: F401
import httpx
import os
from datetime import datetime
import time
import asyncio
import logging
import sys

# Configurar logging
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

app = FastAPI(title="Search API Service", version="1.0.0")

# Configuration
POKE_API_URL = os.getenv('POKE_API_URL', 'http://localhost:8001')
POKE_STATS_URL = os.getenv('POKE_STATS_URL', 'http://localhost:8002')
POKE_IMAGES_URL = os.getenv('POKE_IMAGES_URL', 'http://localhost:8003')
LOGGING_SERVICE_URL = os.getenv('LOGGING_SERVICE_URL', 'http://localhost:8004')


# ==================== Models ====================
class StatEntry(BaseModel):
    """Un stat individual de un Pokemon"""
    name: str
    value: int


class SearchResult(BaseModel):
    """Resultado de búsqueda completo"""
    name: str
    stats: List[StatEntry] = []
    images: Optional[str] = None


# ==================== Logging Helper ====================
async def send_log(api: str, function: str, message: str, level: str = "INFO", latency_ms: float = None):
    """Envía un log al servicio centralizado"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "module": "SEARCH_API",
                "api": api,
                "function": function,
                "message": message,
                "level": level,
                "latency_ms": latency_ms
            }
            response = await client.post(f"{LOGGING_SERVICE_URL}/logs", json=payload, timeout=5.0)

            if response.status_code == 200:
                logger.info(f"Log sent: {api}.{function}")
            else:
                logger.warning(f"Log send failed with status {response.status_code}")

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to logging service: {e}")
    except httpx.TimeoutException as e:
        logger.error(f"Timeout sending log: {e}")
    except Exception as e:
        logger.error(f"Error sending log: {e}", exc_info=True)


# ==================== Helper Functions ====================
async def get_pokemon_from_api(pokemon_name: str, session: httpx.AsyncClient):
    """Obtiene datos de POKE API"""
    try:
        response = await session.get(
            f"{POKE_API_URL}/pokemon/{pokemon_name}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('data')
        return None
    except Exception as e:
        print(f"Error getting Pokemon from API: {e}")
        return None


async def get_pokemon_stats(pokemon_name: str, session: httpx.AsyncClient):
    """Obtiene estadísticas de POKE Stats"""
    try:
        response = await session.get(
            f"{POKE_STATS_URL}/stats/{pokemon_name}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data'):
                return data['data']
        return None
    except Exception as e:
        print(f"Error getting Pokemon stats: {e}")
        return None


async def get_pokemon_images(pokemon_name: str, session: httpx.AsyncClient):
    """Obtiene imágenes de POKE Images"""
    try:
        response = await session.get(
            f"{POKE_IMAGES_URL}/images/{pokemon_name}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('images'):
                return [{"filename": img['filename'], "path": img['path']} for img in data['images']]
        return []
    except Exception as e:
        print(f"Error getting Pokemon images: {e}")
        return []


# ==================== Endpoints ====================
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "search_api",
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }


@app.get("/poke/search", response_model=SearchResult, tags=["Search"])
async def search_pokemon(pokemon_name: str):
    """
    Realiza búsqueda completa de un Pokemon

    Orquesta llamadas a:
    1. POKE API (datos de PokeAPI)
    2. POKE Stats (estadísticas de BD local)
    3. POKE Images (imágenes disponibles)

    Retorna:
    {
        "name": "pokemonName",
        "stats": [{"name": "hp", "value": 35}, ...],
        "images": "http://host/static/pokemon/0.jpg"
    }

    Ejemplo: GET /poke/search?pokemon_name=pikachu
    """
    start_time = time.time()

    try:
        if not pokemon_name or pokemon_name.strip() == "":
            raise HTTPException(status_code=400, detail="pokemon_name parameter is required")

        pokemon_name_clean = pokemon_name.strip().lower()

        # Usar sesión compartida para mejor rendimiento
        async with httpx.AsyncClient() as session:
            # Llamadas paralelas a los tres microservicios
            api_data, stats_data, images_data = await asyncio.gather(
                get_pokemon_from_api(pokemon_name_clean, session),
                get_pokemon_stats(pokemon_name_clean, session),
                get_pokemon_images(pokemon_name_clean, session),
                return_exceptions=True
            )

        latency_ms = (time.time() - start_time) * 1000

        # Validar que al menos tenemos datos de la API
        if not api_data:
            await send_log(
                api="GET_SEARCH",
                function="search_pokemon",
                message=f"Pokemon no encontrado: {pokemon_name}",
                level="WARNING",
                latency_ms=latency_ms
            )
            raise HTTPException(status_code=404, detail=f"Pokemon '{pokemon_name}' not found")

        # Procesar estadísticas → lista de {name, value}
        stats = []
        if stats_data and not isinstance(stats_data, Exception):
            stat_keys = [
                ("hp", "hp"),
                ("attack", "attack"),
                ("defense", "defense"),
                ("sp_atk", "sp_atk"),
                ("sp_def", "sp_def"),
                ("speed", "speed"),
            ]
            for key, label in stat_keys:
                if key in stats_data:
                    stats.append(StatEntry(name=label, value=stats_data[key]))

        # Procesar imágenes → URL de la primera imagen disponible (o None)
        image_url = None
        if isinstance(images_data, list) and images_data:
            first = images_data[0]
            image_url = f"{POKE_IMAGES_URL}{first['path']}"

        # Construir respuesta
        result = SearchResult(
            name=api_data.get('name', pokemon_name_clean),
            stats=stats,
            images=image_url,
        )

        # Enviar log
        await send_log(
            api="GET_SEARCH",
            function="search_pokemon",
            message=f"Búsqueda completada para: {result.name}",
            level="INFO",
            latency_ms=latency_ms
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        await send_log(
            api="GET_SEARCH",
            function="search_pokemon",
            message=f"Search error: {str(e)}",
            level="ERROR",
            latency_ms=latency_ms
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/poke/status", tags=["Status"])
async def check_services_status():
    """
    Verifica el estado de todos los microservicios

    Ejemplo: GET /poke/status
    """
    status_results = {
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "services": {}
    }

    services = {
        "poke_api": POKE_API_URL,
        "poke_stats": POKE_STATS_URL,
        "poke_images": POKE_IMAGES_URL,
        "logging_service": LOGGING_SERVICE_URL
    }

    async with httpx.AsyncClient() as session:
        for service_name, service_url in services.items():
            try:
                response = await session.get(f"{service_url}/health", timeout=5)
                status_results["services"][service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "url": service_url,
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            except Exception as e:
                status_results["services"][service_name] = {
                    "status": "error",
                    "url": service_url,
                    "error": str(e)
                }

    return status_results


if __name__ == '__main__':
    import uvicorn
    import asyncio

    uvicorn.run(app, host='0.0.0.0', port=8000)
