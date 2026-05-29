"""
POKE API Microservice
Consume datos de la API externa de Pokemon (pokeapi.co)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests
import os
from datetime import datetime
import time
import httpx

app = FastAPI(title="POKE API Service", version="1.0.0")

# Configuration
POKEAPI_BASE_URL = os.getenv('POKEAPI_BASE_URL', 'https://pokeapi.co/api/v2')
LOGGING_SERVICE_URL = os.getenv('LOGGING_SERVICE_URL', 'http://localhost:8004')


# ==================== Models ====================
class PokemonInfo(BaseModel):
    """Información básica de un Pokemon desde PokeAPI"""
    id: int
    name: str
    height: int
    weight: int
    base_experience: Optional[int] = None
    is_default: bool


class PokemonResponse(BaseModel):
    """Respuesta con información de Pokemon"""
    success: bool
    data: Optional[PokemonInfo] = None
    message: str


# ==================== Logging Helper ====================
async def send_log(api: str, function: str, message: str, level: str = "INFO", latency_ms: float = None):
    """Envía un log al servicio centralizado"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "module": "POKE_API",
                "api": api,
                "function": function,
                "message": message,
                "level": level,
                "latency_ms": latency_ms
            }
            await client.post(f"{LOGGING_SERVICE_URL}/logs", json=payload, timeout=5.0)
    except Exception as e:
        print(f"Error sending log: {e}")


# ==================== Endpoints ====================
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "poke_api",
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }


@app.get("/pokemon/{name_or_id}", response_model=PokemonResponse, tags=["Pokemon"])
async def get_pokemon(name_or_id: str):
    """
    Obtiene información de un Pokemon desde PokeAPI

    El parámetro puede ser:
    - Nombre del Pokemon (ej: pikachu)
    - ID numérico (ej: 25)

    Ejemplo: GET /pokemon/pikachu
    Ejemplo: GET /pokemon/25
    """
    start_time = time.time()

    try:
        # Hacer request a PokeAPI
        url = f"{POKEAPI_BASE_URL}/pokemon/{name_or_id.lower()}"

        response = requests.get(url, timeout=10)

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 200:
            data = response.json()

            pokemon_info = PokemonInfo(
                id=data['id'],
                name=data['name'],
                height=data['height'],
                weight=data['weight'],
                base_experience=data.get('base_experience'),
                is_default=data.get('is_default', True)
            )

            # Enviar log
            await send_log(
                api="GET_POKEMON",
                function="get_pokemon",
                message=f"Pokemon obtenido de PokeAPI: {pokemon_info.name} (ID: {pokemon_info.id})",
                level="INFO",
                latency_ms=latency_ms
            )

            return PokemonResponse(
                success=True,
                data=pokemon_info,
                message="Pokemon data retrieved successfully"
            )

        elif response.status_code == 404:
            await send_log(
                api="GET_POKEMON",
                function="get_pokemon",
                message=f"Pokemon no encontrado en PokeAPI: {name_or_id}",
                level="WARNING",
                latency_ms=latency_ms
            )

            raise HTTPException(
                status_code=404,
                detail=f"Pokemon '{name_or_id}' not found in PokeAPI"
            )
        else:
            await send_log(
                api="GET_POKEMON",
                function="get_pokemon",
                message=f"PokeAPI error: Status {response.status_code}",
                level="ERROR",
                latency_ms=latency_ms
            )

            raise HTTPException(
                status_code=response.status_code,
                detail="Error fetching from PokeAPI"
            )

    except requests.Timeout:
        latency_ms = (time.time() - start_time) * 1000
        await send_log(
            api="GET_POKEMON",
            function="get_pokemon",
            message=f"PokeAPI timeout al buscar: {name_or_id}",
            level="ERROR",
            latency_ms=latency_ms
        )
        raise HTTPException(status_code=504, detail="PokeAPI request timeout")

    except requests.RequestException as e:
        latency_ms = (time.time() - start_time) * 1000
        await send_log(
            api="GET_POKEMON",
            function="get_pokemon",
            message=f"PokeAPI request error: {str(e)}",
            level="ERROR",
            latency_ms=latency_ms
        )
        raise HTTPException(status_code=502, detail="Error connecting to PokeAPI")

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        await send_log(
            api="GET_POKEMON",
            function="get_pokemon",
            message=f"Unexpected error: {str(e)}",
            level="ERROR",
            latency_ms=latency_ms
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pokemon/{name_or_id}/raw", tags=["Pokemon"])
async def get_pokemon_raw(name_or_id: str):
    """
    Obtiene la respuesta completa (sin procesar) de PokeAPI

    Útil para acceso a más campos

    Ejemplo: GET /pokemon/pikachu/raw
    """
    start_time = time.time()

    try:
        url = f"{POKEAPI_BASE_URL}/pokemon/{name_or_id.lower()}"
        response = requests.get(url, timeout=10)

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 200:
            await send_log(
                api="GET_POKEMON_RAW",
                function="get_pokemon_raw",
                message=f"Raw data retrieved: {name_or_id}",
                level="INFO",
                latency_ms=latency_ms
            )
            return response.json()
        else:
            await send_log(
                api="GET_POKEMON_RAW",
                function="get_pokemon_raw",
                message=f"PokeAPI error: Status {response.status_code}",
                level="ERROR",
                latency_ms=latency_ms
            )
            raise HTTPException(status_code=response.status_code, detail="PokeAPI error")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
